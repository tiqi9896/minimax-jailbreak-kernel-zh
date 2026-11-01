# Usage & Measurement Methodology


**Language:** English | [Chinese (zh-CN)](USAGE.md)

The plugin is easy to install. The hard part is **knowing whether it actually
changed the model's behavior**. This document is the method.

---

## 1. Layered diagnosis — diagnose before you touch anything

"Model didn't do the work" has **three distinct shapes**. They have different
causes and different fixes; diagnosing wrong wastes everything downstream.

Look at four fields in the response: `HTTP status`, `stop_reason`,
`body length`, `usage.output_tokens_details.thinking_tokens`.

| Shape | How to identify | Root cause | Fix |
|---|---|---|---|
| **Behavioral refusal** | Body present, matches refusal phrases | The model's own alignment | Prompt-level kernel |
| **Thinking budget exhausted** | `stop_reason=max_tokens` + body **0 chars** + `thinking_tokens ≈ limit` | Thinking consumed the entire output budget | Lower thinking depth / raise output limit |
| **Tool-call turn** | `stop_reason=tool_use` + empty body | The model is calling a tool; text comes next turn | **Not a failure** |

Two traps that produce false alarms:

- **A tool-call turn looks like an empty response.** Always check
  `stop_reason` before treating "no text" as a refusal.
- **An exhausted thinking budget looks like a refusal.** The model was
  thinking, never got to output. No amount of prompt work fixes it.

## 2. Pick the lever by feasibility, not by hope

1. **Thinking-budget / effort knob** — first find out which parameter the
   provider *actually* honors (`output_config.effort` /
   `reasoning_effort` / `thinking.budget_tokens` / `enable_thinking`), then
   **measure**. The framework's default is frequently not what the provider
   reads.
2. **Prompt kernel** — any model with a system-prompt channel.
3. **Routing / relay** — the same model id can differ by one alignment tier
   across upstreams.
4. **Weight-level (abliteration)** — only viable if you can actually hold the
   weights. Compute total params × bytes-per-param against your VRAM first;
   if it is an order of magnitude off, drop the idea. **Open weights ≠
   runnable on your machine.**

## 3. A/B measurement — the only way to disprove

- **One variable at a time.** Kernel on vs off (or effort high vs low).
  Same cases, same `max_tokens`, same temperature, same effort otherwise.
- **Fixed case set.** Store it as a file; reuse the identical set every run.
- **Classify the result** with the verdict function in
  `skill/llm-refusal-bypass/references/refusal-verdicts.md`:
  `COMPLY` / `SOFT-REFUSE` / `HARD-REFUSE` / `TRUNCATED` / `COMPLY(tool_use)`.
  - ★ Verdict needs **two signals**: a refusal phrase **and** absence of a
    substantive deliverable. Matching only the phrase misclassifies
    "delivered the content but tacked on a disclaimer" as a hard refusal.
- **Verify in the production path**, not only in a synthetic harness. Read the
  real gateway log for middleware hit records. A passing script proves
  nothing about the live system.
- **Check the `model` field** in the response body to confirm you were not
  silently downgraded to another model.
- **Always report the control group.** Experimental numbers alone are not a
  proof.

### Tool-call turns must be excluded from the refusal count

If your case set lets the model use tools, a `tool_use` turn is a normal
first turn. Counting it as a refusal makes the numbers lie in the pessimistic
direction — and it is the single most common false positive.

## 4. Applying the kernel correctly (Anthropic-compatible routes)

Two shape traps bite here, and both fail **silently**:

- **`system` lives at the top level** of the request body in Anthropic
  compatible mode. There is **no** `role="system"` message in `messages`. A
  plugin that only scans `messages` will register, log, send the request, and
  have **zero effect**.
- **`thinking.budget_tokens` is ignored** by MiniMax M3.1-Flash. Only
  `output_config.effort` (adaptive thinking) works. Hermes' default code path
  routes MiniMax into the manual-`budget_tokens` branch, which means effort
  was never actually applied.

## 5. Guarantee coverage across sessions

System-prompt sections are **frozen per session** at creation time and
persisted. A session created before the plugin was enabled therefore has no
kernel in its stored prompt.

Three mechanisms, use all three:

| Mechanism | What it covers |
|---|---|
| `hermes sessions refresh-prompts` | Stored prompts rebuild on the session's **next activity** (one prompt-cache miss) |
| **Request-layer fallback** | If the outgoing system prompt has no kernel marker, inject it **right then** — covers sessions that have never been resumed |
| New sessions | The section is registered automatically |

★ The request-layer fallback is the one that closes the gap. The other two only
cover sessions that have been touched.

### Route detection: model name beats base_url

In a fallback chain the `base_url` can still be the MiniMax endpoint while the
model has already swapped to another provider. Detect the route by **model
name**, and fall back to `base_url` only when the model name is missing or
generic. Otherwise you will inject a MiniMax kernel into another provider's
system prompt.

## 6. Practical notes

- **Keep the prompt budget bounded.** The kernel ships as two segments
  (`strict` = the main contract, `reinforce` = delivery-fidelity rules).
  Keep the total under the provider's per-section limit; both segments must
  fit.
- **Two segments, not one duplicated text.** The main contract governs *what
  to do*; the reinforcement governs *how it must not be downgraded*. Merging
  them into one blob measurably weakens both.
- **Watch the plan quota.** Large-budget regression runs will exhaust a
  metered plan. Serialize them, use layered budgets, and stop immediately on
  a quota error — do not let 429s contaminate your refusal statistics.
- **Check the profile name is what you think.** `profile` selects the text;
  `effort` selects the depth. They are independent knobs.

## 7. Legal & ethical scope

This tool shapes how a model behaves toward **your** requests on **your** API
key. It cannot and does not defeat provider-side enforcement. Use it only for
work you are authorized to perform, and respect your provider's terms of
service and applicable law.
