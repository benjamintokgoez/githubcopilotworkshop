# Challenge 1 — Code Comprehension

## Objective

Use GitHub Copilot to understand this unfamiliar, complex codebase without reading every line of code. Build a mental model of the architecture, dependencies, and domain concepts.

## Recommended Model

**Claude Sonnet 4** — Excellent at synthesising complex codebases and explaining patterns.

## Background

You've just joined the QuantCore team. The codebase is a quantitative trading engine with advanced Python patterns:
- Metaclasses for strategy registration
- Descriptors for cached Greek computation
- Async generators for market data streaming
- Protocol classes for structural subtyping
- `__slots__` for performance-critical objects
- Operator overloading for portfolio arithmetic
- Event sourcing with replay capabilities

Your task: **understand it all in 45 minutes, using Copilot as your guide.**

## Tasks

### Task 1: Architecture Overview (10 min)

Use Copilot Chat to ask high-level questions about the codebase:

1. Ask Copilot to explain the overall architecture of this project
2. Ask what design patterns are used and why
3. Ask Copilot to generate a module dependency diagram

**Hint**: Select multiple files and ask Copilot to explain their relationships.

### Task 2: Core Domain Model (10 min)

Deep-dive into the domain models:

1. Open `qxm/core/models.py` and ask Copilot to explain the data model hierarchy
2. Ask about the `TickSize` custom type — what pattern does it use?
3. Ask Copilot to explain the `Order` model's state machine (status transitions)

### Task 3: Advanced Patterns (15 min)

Investigate the advanced Python patterns:

1. **Metaclass**: Open `qxm/strategy/base.py` and ask Copilot to explain `StrategyMeta`
   - What is the registry pattern?
   - How does auto-registration work?

2. **Descriptor**: Open `qxm/risk/greeks.py` and ask about `CachedGreek`
   - How does cache invalidation work?
   - What is `__set_name__` used for?

3. **Event Sourcing**: Open `qxm/core/events.py` and ask about the `EventBus`
   - How do async generators enable streaming?
   - What's the difference between callback and generator modes?

### Task 4: Documentation Generation (10 min)

Ask Copilot to help you create documentation:

1. Generate a Mermaid class diagram for the core models
2. Generate a sequence diagram for the order matching flow
3. Create a glossary of domain terms (ask Copilot to extract them from the code)

## Stretch Goals

- Ask Copilot to identify potential performance bottlenecks in the matching engine
- Ask Copilot to compare the event sourcing implementation to industry standards
- Generate a C4 architecture diagram from the codebase
- Ask Copilot about the trade-offs of using `__slots__` on the `Tick` class

## Deliverables

By the end of this challenge, you should be able to explain:
1. What QuantCore does at a high level
2. How orders flow through the system (submit → match → fill → position update)
3. At least 3 advanced Python patterns used, and why they're appropriate

## Time

~45 minutes

---

*Next: [Challenge 2 — Debugging](./challenge_02_debugging.md)*
