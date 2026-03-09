"""Security audit script — scans the codebase for known vulnerability patterns.

Run with: python security_check.py

This script is intentionally provided so attendees can see the kind
of issues they need to fix in Challenge 5.  It performs *static*
pattern matching (not bandit) to stay simple and portable.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class Finding:
    file: str
    line: int
    severity: str
    category: str
    description: str


PATTERNS = [
    {
        "pattern": r"pickle\.loads?\(",
        "severity": "HIGH",
        "category": "Insecure Deserialisation",
        "description": "pickle.loads() can execute arbitrary code from untrusted data.",
    },
    {
        "pattern": r"""f['\"].*SELECT.*\{.*\}""",
        "severity": "CRITICAL",
        "category": "SQL Injection",
        "description": "SQL query built with f-string interpolation of user input.",
    },
    {
        "pattern": r"random\.choice|random\.randint|random\.random\(",
        "severity": "MEDIUM",
        "category": "Insecure Randomness",
        "description": "Using random module (Mersenne Twister) for security-sensitive operations. Use secrets module.",
    },
    {
        "pattern": r"""(?:secret|key|password|token)\s*=\s*['\"][^'\"]{8,}['\"]""",
        "severity": "HIGH",
        "category": "Hardcoded Secret",
        "description": "Potential hardcoded secret/key found in source code.",
    },
    {
        "pattern": r"==\s*(?:hashed|signature|token|key|password)",
        "severity": "MEDIUM",
        "category": "Timing Attack",
        "description": "Direct string comparison for secrets. Use hmac.compare_digest().",
    },
    {
        "pattern": r"allow_origins\s*=\s*\[\s*['\"]?\*['\"]?\s*\]",
        "severity": "LOW",
        "category": "CORS Misconfiguration",
        "description": "CORS allows all origins (*). Should be restricted in production.",
    },
]

SCAN_DIRS = ["qxm"]
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv"}


def scan_file(filepath: Path) -> List[Finding]:
    """Scan a single Python file for security patterns."""
    findings = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        return findings

    for i, line in enumerate(content.splitlines(), start=1):
        for pat in PATTERNS:
            if re.search(pat["pattern"], line, re.IGNORECASE):
                findings.append(Finding(
                    file=str(filepath),
                    line=i,
                    severity=pat["severity"],
                    category=pat["category"],
                    description=pat["description"],
                ))
    return findings


def scan_project(root: Path) -> List[Finding]:
    """Scan all Python files under the given root."""
    all_findings = []
    for scan_dir in SCAN_DIRS:
        target = root / scan_dir
        if not target.exists():
            continue
        for py_file in target.rglob("*.py"):
            if any(skip in py_file.parts for skip in SKIP_DIRS):
                continue
            all_findings.extend(scan_file(py_file))
    return all_findings


def print_report(findings: List[Finding]) -> None:
    """Print a formatted security report."""
    if not findings:
        print("\n✅ No security issues found!")
        return

    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    findings.sort(key=lambda f: severity_order.get(f.severity, 99))

    print("\n" + "=" * 70)
    print("  QuantCore Security Audit Report")
    print("=" * 70)
    print(f"\n  Total findings: {len(findings)}\n")

    for f in findings:
        icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}.get(f.severity, "⚪")
        print(f"  {icon} [{f.severity}] {f.category}")
        print(f"     File: {f.file}:{f.line}")
        print(f"     {f.description}")
        print()

    print("=" * 70)
    critical = sum(1 for f in findings if f.severity == "CRITICAL")
    high = sum(1 for f in findings if f.severity == "HIGH")
    print(f"  Summary: {critical} CRITICAL, {high} HIGH, "
          f"{len(findings) - critical - high} other")
    print("=" * 70)


def main() -> int:
    root = Path(__file__).resolve().parent
    findings = scan_project(root)
    print_report(findings)
    # Exit with non-zero if any HIGH or CRITICAL findings
    if any(f.severity in ("CRITICAL", "HIGH") for f in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
