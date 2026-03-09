# Challenge 0 — Setup & Environment

## Objective

Get your development environment ready and verify all dependencies are working.

## Prerequisites

- Python 3.11+
- VS Code with GitHub Copilot extension
- GitHub Copilot Chat (with access to Claude Sonnet 4, GPT-4o, and o3 models)

## Steps

### 1. Clone the repository

```bash
git clone <repo-url>
cd quantcore
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Generate sample data

```bash
python scripts/generate_sample_data.py
```

### 5. Verify the setup

Try running the tests:

```bash
pytest tests/ -v
```

> **Note**: Some tests are *expected* to fail — you'll fix them in later challenges!

### 6. Explore the project structure

Open VS Code and look around the repository structure:

```
quantcore/
├── qxm/                    # Main package
│   ├── core/               # Order book, matching engine, events
│   ├── risk/               # VaR, Greeks, portfolio analytics
│   ├── data/               # Market data feed, storage, transforms
│   ├── strategy/           # Trading strategies (metaclass-based)
│   ├── auth/               # API key management, request signing
│   ├── utils/              # Serialisation, decorators, metrics
│   ├── api/                # FastAPI REST endpoints
│   └── mcp_server/         # MCP server (Challenge 6)
├── tests/                  # Test suite
├── dashboard/              # Web dashboard (Challenge 7)
├── challenges/             # Challenge descriptions (you are here!)
├── scripts/                # Utility scripts
├── settings.yaml           # Configuration
├── instruments.json        # Instrument definitions
└── main.py                 # Application entry point
```

### 7. Configure GitHub Copilot

Make sure you can access different models in GitHub Copilot:
1. Open GitHub Copilot Chat (⌘+I or Ctrl+I)
2. Check the model selector dropdown
3. Verify you have access to **Claude Sonnet 4**, **GPT-4o**, and **o3**

## Verification

You're ready when:
- [x] Virtual environment is active
- [x] Dependencies installed without errors
- [x] Sample data generated in `sample_data/`
- [x] You can open the project in VS Code
- [x] GitHub Copilot Chat is working

## Time Estimate

~15 minutes

---

*Next: [Challenge 1 — Code Comprehension](./challenge_01_comprehension.md)*
