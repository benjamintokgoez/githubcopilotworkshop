# QuantCore — Advanced GitHub Copilot Workshop

A complex quantitative trading engine built in Python, designed as a hands-on workshop for learning GitHub Copilot's advanced features.

## What You'll Learn

| Challenge | Copilot Feature | AI Model | Duration |
|-----------|----------------|----------|----------|
| 0. Setup | — | — | 30 min |
| 1. Code Comprehension | Chat, `/explain` | Claude Sonnet 4 | 60 min |
| 2. Debugging | Chat, Agent Mode | Claude Sonnet 4 | 60 min |
| 3. Mathematical Bug Fixes | Chat | o3 | 60 min |
| 4. Pydantic v1 → v2 Migration | Agent Mode | Claude Sonnet 4 | 60 min |
| 5. Security Hardening | Chat, Agent Mode | Claude Sonnet 4 | 45 min |
| 6. MCP Server Extension | Agent Mode | Claude Sonnet 4 | 60 min |
| 7. Dashboard Feature Build | Agent Mode | GPT-4o | 75 min |

## Prerequisites

- Python 3.11 or later
- VS Code with GitHub Copilot extension
- Active GitHub Copilot licence (Individual, Business, or Enterprise)

## Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd githubcopilotworkshop

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"

# Generate sample data
python scripts/generate_sample_data.py

# Verify setup
pytest tests/ -v

# Start the server
python main.py
```

## Project Structure

```
githubcopilotworkshop/
├── qxm/                          # Main package (Quantitative eXchange Module)
│   ├── core/                     # Order matching engine, order book, events, models
│   ├── risk/                     # VaR, Black-Scholes Greeks, portfolio analytics
│   ├── data/                     # Market data feeds, time-series store, transforms
│   ├── strategy/                 # Strategy framework with metaclass auto-registration
│   ├── auth/                     # HMAC signing, API key management
│   ├── api/                      # FastAPI REST endpoints and middleware
│   ├── mcp_server/               # MCP (Model Context Protocol) server
│   └── utils/                    # Serialisers, decorators, metrics
├── tests/                        # Unit tests
├── challenges/                   # Workshop challenge instructions
├── dashboard/                    # Trading dashboard (HTML/JS)
├── scripts/                      # Data generation scripts
├── main.py                       # Application entry point
├── settings.yaml                 # Configuration
└── instruments.json              # Instrument definitions
```

## Workshop Challenges

Start with [Challenge 0: Setup](challenges/challenge_00_setup.md) and work through sequentially:

1. [Challenge 1: Code Comprehension](challenges/challenge_01_comprehension.md)
2. [Challenge 2: Debugging](challenges/challenge_02_debugging.md)
3. [Challenge 3: Mathematical Bug Fixes](challenges/challenge_03_math_bugs.md)
4. [Challenge 4: Pydantic v1 → v2 Migration](challenges/challenge_04_pydantic_migration.md)
5. [Challenge 5: Security Hardening](challenges/challenge_05_security.md)
6. [Challenge 6: MCP Server Extension](challenges/challenge_06_mcp_server.md)
7. [Challenge 7: Dashboard Feature Build](challenges/challenge_07_dashboard.md)

## For Proctors

The `proctor/` directory contains solution guides with:
- Exact Copilot prompts that produce good results
- Step-by-step solutions for each bug/task
- Common pitfalls and how to help attendees
- Timing guidance

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for a detailed overview of the system design, module relationships, and advanced Python patterns used.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## Licence

MIT — This is a workshop repository intended for educational use.
