"""Small AST-based security scanner for the MittelWerk Python source tree.

Run ``python security_check.py`` for stable plain text or add ``--json`` for
machine-readable output. The scanner reports locations and descriptions only;
it never echoes source lines that could contain credentials.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    """One static-analysis finding."""

    file: str
    line: int
    severity: str
    category: str
    description: str


SCAN_DIRS = ("mittelwerk",)
SKIP_DIRS = frozenset({"__pycache__", ".git", "node_modules", ".venv"})
FAIL_SEVERITIES = frozenset({"CRITICAL", "HIGH"})
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

_SECRET_NAME = re.compile(
    r"(?:^|_)(?:secret|password|passwd|token|api_?key|private_?key|"
    r"signing_?key|encryption_?key|key)(?:$|_)",
    re.IGNORECASE,
)
_SECURITY_FUNCTION = re.compile(
    r"(?:generate|create|issue|rotate|derive|reset).*(?:secret|password|token|key)"
    r"|(?:secret|password|token|key).*(?:generate|create|issue|rotate|derive)",
    re.IGNORECASE,
)
_PLACEHOLDER_SECRET = re.compile(
    r"^(?:change[-_ ]?me|example|placeholder|your[-_ ]|dummy|test|none|null)",
    re.IGNORECASE,
)
_SQL_WORD = re.compile(r"\b(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER)\b", re.IGNORECASE)
_RANDOM_CALLS = frozenset(
    {
        "random.choice",
        "random.choices",
        "random.randint",
        "random.randrange",
        "random.random",
        "random.getrandbits",
        "random.randbytes",
    }
)
_DESERIALIZATION_CALLS = {
    "pickle.load": ("HIGH", "Unsafe Deserialization", "pickle.load can execute code."),
    "pickle.loads": ("HIGH", "Unsafe Deserialization", "pickle.loads can execute code."),
    "dill.load": ("HIGH", "Unsafe Deserialization", "dill.load can execute code."),
    "dill.loads": ("HIGH", "Unsafe Deserialization", "dill.loads can execute code."),
    "marshal.loads": (
        "HIGH",
        "Unsafe Deserialization",
        "marshal.loads must not process untrusted data.",
    ),
}
_WEAK_HASH_CALLS = frozenset({"hashlib.md5", "hashlib.sha1"})


def _integrity_finding(
    filename: str,
    description: str,
    line: int = 1,
) -> Finding:
    return Finding(
        file=filename,
        line=max(1, line),
        severity="HIGH",
        category="Scanner Integrity",
        description=description,
    )


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _target_names(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        return (node.attr,)
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(name for item in node.elts for name in _target_names(item))
    return ()


def _contains_call(node: ast.AST, names: frozenset[str]) -> bool:
    return any(
        isinstance(item, ast.Call) and _call_name(item.func) in names for item in ast.walk(node)
    )


def _contains_secret_reference(node: ast.AST) -> bool:
    return any(
        _SECRET_NAME.search(name) is not None
        for item in ast.walk(node)
        for name in _target_names(item)
    )


def _is_secret_target(name: str) -> bool:
    if not _SECRET_NAME.search(name):
        return False
    normalized = name.lower()
    return not normalized.endswith(("_prefix", "_suffix", "_header", "_name", "_id", "_length"))


def _dynamic_sql(node: ast.AST) -> bool:
    if isinstance(node, ast.JoinedStr):
        text = "".join(
            part.value
            for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
        return bool(_SQL_WORD.search(text))
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        constants = " ".join(
            str(item.value)
            for item in ast.walk(node)
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        )
        return bool(_SQL_WORD.search(constants))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "format":
            template = node.func.value
            return (
                isinstance(template, ast.Constant)
                and isinstance(template.value, str)
                and bool(_SQL_WORD.search(template.value))
                and bool(node.args or node.keywords)
            )
    return False


def _is_wildcard_origins(node: ast.AST) -> bool:
    return isinstance(node, (ast.List, ast.Tuple, ast.Set)) and any(
        isinstance(item, ast.Constant) and item.value == "*" for item in node.elts
    )


class _SecurityVisitor(ast.NodeVisitor):
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.findings: list[Finding] = []
        self._functions: list[str] = []
        self._dynamic_sql_names: list[set[str]] = [set()]

    def _add(
        self,
        node: ast.AST,
        severity: str,
        category: str,
        description: str,
    ) -> None:
        self.findings.append(
            Finding(
                file=self.filename,
                line=getattr(node, "lineno", 1),
                severity=severity,
                category=category,
                description=description,
            )
        )

    def _check_hardcoded_secret(self, target: ast.AST, value: ast.AST) -> None:
        names = _target_names(target)
        if not any(_is_secret_target(name) for name in names):
            return
        if (
            isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and len(value.value) >= 8
            and not _PLACEHOLDER_SECRET.search(value.value)
        ):
            self._add(
                value,
                "HIGH",
                "Hardcoded Secret",
                "A credential-like variable contains a hardcoded string.",
            )
        if _contains_call(value, _RANDOM_CALLS):
            self._add(
                value,
                "HIGH",
                "Weak Key Randomness",
                "Security credentials must use the secrets module or a CSPRNG.",
            )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._functions.append(node.name)
        self._dynamic_sql_names.append(set())
        self.generic_visit(node)
        self._dynamic_sql_names.pop()
        self._functions.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._functions.append(node.name)
        self._dynamic_sql_names.append(set())
        self.generic_visit(node)
        self._dynamic_sql_names.pop()
        self._functions.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._check_hardcoded_secret(target, node.value)
            if _dynamic_sql(node.value):
                self._dynamic_sql_names[-1].update(_target_names(target))
            if any(name == "allow_origins" for name in _target_names(target)):
                if _is_wildcard_origins(node.value):
                    self._add(
                        node,
                        "LOW",
                        "Unsafe CORS",
                        "CORS permits every origin.",
                    )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._check_hardcoded_secret(node.target, node.value)
            if _dynamic_sql(node.value):
                self._dynamic_sql_names[-1].update(_target_names(node.target))
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and _is_secret_target(key.value)
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and len(value.value) >= 8
                and not _PLACEHOLDER_SECRET.search(value.value)
            ):
                self._add(
                    value,
                    "HIGH",
                    "Hardcoded Secret",
                    "A credential field contains a hardcoded string.",
                )
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        if (
            node.value is not None
            and self._functions
            and _SECURITY_FUNCTION.search(self._functions[-1])
            and _contains_call(node.value, _RANDOM_CALLS)
        ):
            self._add(
                node,
                "HIGH",
                "Weak Key Randomness",
                "Security credentials must use the secrets module or a CSPRNG.",
            )
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        operands = (node.left, *node.comparators)
        if any(isinstance(operator, (ast.Eq, ast.NotEq)) for operator in node.ops) and any(
            _contains_secret_reference(operand) for operand in operands
        ):
            self._add(
                node,
                "MEDIUM",
                "Direct Secret Comparison",
                "Use hmac.compare_digest for secret or signature comparisons.",
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name in _DESERIALIZATION_CALLS:
            self._add(node, *_DESERIALIZATION_CALLS[name])
        elif name in {"eval", "builtins.eval", "exec", "builtins.exec"}:
            self._add(
                node,
                "CRITICAL",
                "Dynamic Code Execution",
                "eval or exec can execute attacker-controlled code.",
            )
        elif name in {"yaml.unsafe_load", "yaml.full_load"}:
            self._add(
                node,
                "HIGH",
                "Unsafe Deserialization",
                "Use yaml.safe_load for untrusted input.",
            )
        elif name == "yaml.load" and not any(
            keyword.arg == "Loader" and _call_name(keyword.value).endswith("SafeLoader")
            for keyword in node.keywords
        ):
            self._add(
                node,
                "HIGH",
                "Unsafe Deserialization",
                "yaml.load requires SafeLoader for untrusted input.",
            )

        if name in _WEAK_HASH_CALLS:
            self._add(
                node,
                "MEDIUM",
                "Weak Cryptography",
                "MD5 and SHA-1 are unsuitable for security-sensitive hashing.",
            )

        if name in {"os.system", "os.popen"}:
            self._add(
                node,
                "HIGH",
                "Shell Execution",
                "Avoid invoking a command through the operating-system shell.",
            )
        elif name in {
            "subprocess.call",
            "subprocess.check_call",
            "subprocess.check_output",
            "subprocess.Popen",
            "subprocess.run",
        } and any(
            keyword.arg == "shell"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        ):
            self._add(
                node,
                "HIGH",
                "Shell Execution",
                "subprocess shell=True permits shell injection.",
            )

        if name.rsplit(".", 1)[-1] in {"execute", "executemany"}:
            if node.args and (
                _dynamic_sql(node.args[0])
                or (
                    isinstance(node.args[0], ast.Name)
                    and node.args[0].id in self._dynamic_sql_names[-1]
                )
            ):
                self._add(
                    node,
                    "CRITICAL",
                    "SQL Injection",
                    "Use parameterized SQL instead of interpolated query text.",
                )

        for keyword in node.keywords:
            if keyword.arg == "allow_origins" and _is_wildcard_origins(keyword.value):
                self._add(
                    keyword.value,
                    "LOW",
                    "Unsafe CORS",
                    "CORS permits every origin.",
                )
            if (
                keyword.arg is not None
                and _SECRET_NAME.search(keyword.arg)
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
                and len(keyword.value.value) >= 8
                and not _PLACEHOLDER_SECRET.search(keyword.value.value)
            ):
                self._add(
                    keyword.value,
                    "HIGH",
                    "Hardcoded Secret",
                    "A credential argument contains a hardcoded string.",
                )

        self.generic_visit(node)


def scan_source(source: str, filename: str = "<memory>") -> list[Finding]:
    """Scan Python source while naturally excluding comments and string contents."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return [
            _integrity_finding(
                filename,
                "Python source could not be parsed; security scan incomplete.",
                exc.lineno or 1,
            )
        ]
    visitor = _SecurityVisitor(filename)
    visitor.visit(tree)
    return _sorted_unique(visitor.findings)


def _sorted_unique(findings: Sequence[Finding]) -> list[Finding]:
    return sorted(
        set(findings),
        key=lambda finding: (
            SEVERITY_ORDER.get(finding.severity, 99),
            finding.file,
            finding.line,
            finding.category,
            finding.description,
        ),
    )


def scan_file(filepath: Path) -> list[Finding]:
    """Scan one Python file without disclosing its source in results."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [
            _integrity_finding(
                str(filepath),
                "Python source is not valid UTF-8; security scan incomplete.",
            )
        ]
    except OSError:
        return [
            _integrity_finding(
                str(filepath),
                "Python source could not be read; security scan incomplete.",
            )
        ]
    return scan_source(content, str(filepath))


def scan_project(
    root: Path,
    scan_dirs: Sequence[str] = SCAN_DIRS,
) -> list[Finding]:
    """Scan Python files below selected project directories."""
    findings: list[Finding] = []
    for scan_dir in scan_dirs:
        target = root / scan_dir
        if not target.exists():
            continue
        for py_file in sorted(target.rglob("*.py")):
            if any(part in SKIP_DIRS for part in py_file.parts):
                continue
            findings.extend(scan_file(py_file))
    return _sorted_unique(findings)


def print_report(findings: Sequence[Finding]) -> None:
    """Print a deterministic, source-free plain-text report."""
    ordered = _sorted_unique(findings)
    print("MittelWerk Security Audit")
    print(f"Total findings: {len(ordered)}")
    for finding in ordered:
        print(
            f"{finding.severity} {finding.category} "
            f"{finding.file}:{finding.line} - {finding.description}"
        )
    counts = {
        severity: sum(finding.severity == severity for finding in ordered)
        for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    }
    print("Summary: " + ", ".join(f"{severity}={counts[severity]}" for severity in counts))


def print_json_report(findings: Sequence[Finding]) -> None:
    """Print a deterministic JSON report."""
    ordered = _sorted_unique(findings)
    print(
        json.dumps(
            {
                "findings": [asdict(finding) for finding in ordered],
                "total": len(ordered),
            },
            indent=2,
            sort_keys=True,
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the project scan and return nonzero for high-risk findings."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="project root to scan",
    )
    args = parser.parse_args(argv)
    findings = scan_project(args.root.resolve())
    if args.json:
        print_json_report(findings)
    else:
        print_report(findings)
    return int(any(finding.severity in FAIL_SEVERITIES for finding in findings))


if __name__ == "__main__":
    raise SystemExit(main())
