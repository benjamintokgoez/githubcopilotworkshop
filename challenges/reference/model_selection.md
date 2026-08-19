# Choosing a model (without memorising model names)

This workshop never tells you which model to use. Model line-ups change every few
weeks, availability differs per organisation, and a curriculum built on specific
model names is stale before it is delivered.

**What to do instead:** use **Auto**, or pick a model your administrator has
approved and that actually appears in your picker. Then be able to justify the
choice.

- Auto model selection: <https://docs.github.com/en/copilot/concepts/models/auto-model-selection>
- Change the chat model: <https://docs.github.com/en/copilot/how-tos/use-ai-models/change-the-chat-model>
- Currently supported models: <https://docs.github.com/en/copilot/reference/ai-models/supported-models>
- Compare models for a task: <https://docs.github.com/en/copilot/tutorials/compare-ai-models>

## The five selection factors

Say these out loud when someone asks "why that model?".

| Factor | Question to ask | Pushes you toward |
|---|---|---|
| **Task complexity** | Does this need multi-step reasoning across several files, or is it a local edit? | Deeper reasoning for migrations, architecture, subtle numeric defects; lighter models for renames, summaries, boilerplate |
| **Latency** | Am I in a tight interactive loop, or can I wait and read? | Fast models while exploring; slower, deeper models for a plan you will act on |
| **Policy** | Is the model enabled for my organisation and this surface? | Whatever your admin actually enabled; do not design a workflow around a model you cannot use |
| **Credits / budget** | Does this request consume premium budget my team is tracking? | Cheaper options for exploration, premium for the decision that matters |
| **Evidence needs** | Do I need an inspectable plan, visible tool actions, or long context to trust the result? | Models and modes that expose useful evidence when the output must be defended |

## How to use this in the labs

Every lab asks you to record one line in your evidence notes:

> Model used: `Auto` (or the approved model you selected) - chosen because
> \<factor\> dominated, and I accepted \<trade-off\>.

If you switch mid-task, record why. "I switched after the first plan came back
shallow" is a good, teachable answer. "I always use X" is not.

## Availability and policy reality

- Your picker is the source of truth. If a model is not listed, your organisation
  has not enabled it, and no workshop instruction can change that.
- Enterprise and organisation policies control which models, agents, and surfaces
  are available: <https://docs.github.com/en/copilot/concepts/policies> and
  <https://docs.github.com/en/copilot/reference/supported-surfaces-for-policies>.
- Some plans meter premium requests and support spending budgets. Ask before you
  burn a team budget on a workshop exercise:
  <https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing>
  and <https://docs.github.com/en/copilot/concepts/usage-limits>.
- If nothing works, the labs all have an offline or reduced path. See
  [scenario_tooling.md](scenario_tooling.md).

## Anti-patterns to retire today

- Copying a model name out of a slide deck from last quarter.
- Choosing the "strongest" model for a two-line rename because it feels safer.
- Blaming the model for an outcome that a missing plan, missing context, or
  missing test would have caught.
- Treating model choice as more important than the loop. It is the smallest of the
  five decisions you make in any lab.
