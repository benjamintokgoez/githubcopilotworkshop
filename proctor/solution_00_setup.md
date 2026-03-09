# Proctor Guide — Challenge 0: Setup

## Pre-Workshop Checklist

### Room Setup
- [ ] Each attendee has Python 3.11+ installed
- [ ] Each attendee has VS Code with GitHub Copilot extension
- [ ] Each attendee has an active GitHub Copilot licence (Individual, Business, or Enterprise)
- [ ] Wi-Fi is stable and sufficient for all attendees
- [ ] Projector is working for live demos

### Repository Distribution
- [ ] Clone the repo or distribute a zip of the `main` branch (NOT the `proctor` branch)
- [ ] Verify the repo runs: `pip install -e ".[dev]"` then `pytest tests/`

### Expected Issues & Solutions

**Issue: Python version too old**
```bash
python --version  # Must be 3.11+
# If on macOS: brew install python@3.12
# If on Windows: download from python.org
```

**Issue: `pydantic` version conflict**
```bash
pip install --force-reinstall pydantic==1.10.18
```

**Issue: Copilot not responding**
- Check Copilot icon in VS Code status bar (should be active, not error)
- Try signing out and back in: Ctrl+Shift+P → "GitHub Copilot: Sign Out"
- Verify subscription at https://github.com/settings/copilot

**Issue: Model selection**
- For Copilot Individual: May not have access to all models; Claude Sonnet 4 and GPT-4o should be available
- For Copilot Business/Enterprise: Admin may need to enable model selection
- Fallback: Use the default model if a specific model is unavailable

### Demo Script (10 min)

1. Open the repo in VS Code
2. Show the project structure briefly
3. Open Copilot Chat and demonstrate:
   - Inline completion: Start typing in `main.py`
   - Chat mode: Ask "What does this project do?"
   - Agent Mode: Ask "Explain the architecture of this project"
4. Show model switching in the Chat panel dropdown
5. Explain challenge structure: "We'll work through 7 challenges of increasing complexity"

### Timing Guide

| Time | Activity |
|------|----------|
| 0:00 | Welcome & Setup (Challenge 0) |
| 0:30 | Challenge 1: Comprehension |
| 1:30 | Challenge 2: Debugging |
| 2:30 | *Morning Break* |
| 2:45 | Challenge 3: Math Bugs |
| 3:45 | Challenge 4: Pydantic Migration |
| 4:45 | *Lunch* |
| 5:30 | Challenge 5: Security |
| 6:15 | Challenge 6: MCP Server |
| 7:15 | Challenge 7: Dashboard |
| 8:15 | Wrap-up & Discussion |
