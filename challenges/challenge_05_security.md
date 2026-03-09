# Challenge 5 — Security Hardening

## Objective

Find and fix **6 security vulnerabilities** planted throughout the codebase. This challenge simulates a real security audit where Copilot helps identify and remediate issues.

## Recommended Model

**Claude Sonnet 4** — Excellent at pattern-matching known vulnerability categories and suggesting secure alternatives.

## Background

Before QuantCore can go to production, it must pass a security review. A colleague ran `security_check.py` and flagged several issues, but the report is incomplete. Use Copilot to find *all* vulnerabilities.

## Getting Started

Run the built-in security scanner first:

```bash
python security_check.py
```

This catches some — but not all — of the issues. You'll need Copilot's help to find the rest.

## Vulnerability Catalogue

Find and fix all 6 vulnerabilities:

### Vuln 1: SQL Injection (Critical)

- **File**: `qxm/api/routes.py`
- **Hint**: Look at the `search_instruments` endpoint. How is the query parameter used?
- **Ask Copilot**: "Review the search_instruments route for SQL injection vulnerabilities and suggest a parameterised query fix."

### Vuln 2: Insecure Random Number Generation (High)

- **File**: `qxm/auth/keys.py`
- **Hint**: How are API keys generated? Is `random.choice` cryptographically secure?
- **Ask Copilot**: "Is the key generation in auth/keys.py secure? What should be used instead of random.choice?"

### Vuln 3: Hardcoded Secret (High)

- **File**: `qxm/auth/keys.py`
- **Hint**: Look for `MASTER_SECRET`. Should secrets be in source code?
- **Ask Copilot**: "Find hardcoded secrets in the auth module and show me how to load them from environment variables instead."

### Vuln 4: Unsafe Deserialisation (Critical)

- **File**: `qxm/utils/serializer.py`
- **Hint**: `pickle.loads()` on untrusted data enables arbitrary code execution.
- **Ask Copilot**: "The from_binary function uses pickle.loads. Explain why this is dangerous and provide a safe alternative."

### Vuln 5: Timing Attack (Medium)

- **File**: `qxm/api/middleware.py`
- **Hint**: How is the API key compared? Is `==` safe for secret comparison?
- **Ask Copilot**: "Review the API key validation in middleware.py. Is the comparison timing-safe?"

### Vuln 6: Missing Input Validation (Medium)

- **File**: `qxm/api/routes.py`
- **Hint**: The `submit_order` endpoint doesn't validate quantity or price values. What happens with negative quantities?
- **Ask Copilot**: "Add input validation to the submit_order endpoint. What constraints should quantity and price have?"

## How to Use Copilot

### Strategy 1: Broad Security Scan

Ask Copilot to review the entire codebase:

> "Perform a security audit of this Python project. Focus on OWASP Top 10 vulnerabilities, hardcoded secrets, unsafe deserialisation, and injection attacks. List every issue you find with file, line, severity, and recommended fix."

### Strategy 2: File-by-File Review

For each suspect file, ask targeted questions:

> "Review qxm/api/routes.py for security vulnerabilities. Consider injection, validation, and authentication issues."

### Strategy 3: Fix and Verify

After identifying an issue:

> "Fix the SQL injection in search_instruments by using parameterised queries. Show me the before and after."

## Verification

```bash
# Re-run the security scanner — it should report fewer issues
python security_check.py

# Run tests to ensure fixes don't break functionality
pytest tests/ -v

# Manual verification of specific fixes:
python -c "
from qxm.auth.keys import KeyManager
km = KeyManager()
key = km.generate_key('test', ['read'])
print(f'Key length: {len(key.key)}')
print(f'Key uses secrets module: True')
"
```

## Stretch Goals

- Add **rate limiting** to the API to prevent brute-force attacks on the key validation endpoint
- Implement **request signing verification** using the existing `qxm/auth/signing.py` module in the middleware
- Add **Content Security Policy** headers to the API responses
- Write a test that proves the SQL injection is no longer exploitable
- Add an **audit log** that records all authentication attempts (successes and failures)

## Time

~45 minutes

---

*Next: [Challenge 6 — MCP Server Extension](./challenge_06_mcp_server.md)*
