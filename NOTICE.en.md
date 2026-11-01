# NOTICE — Attribution & Provenance


**Language:** English | [Chinese (zh-CN)](NOTICE)

This repository is a **derived work**. Please read this before redistributing.

## Two copyright holders

| Component | Copyright | License |
|---|---|---|
| `plugin/prompts/profiles/{core,research,creative,max}.md` | © 2026 Enchanted0911 | MIT |
| `plugin/prompts/profiles/{strict,reinforce}.md` | © 2026 tiqi9896 | MIT |
| `plugin/__init__.py`, `plugin/selftest.py`, `plugin/title_extract.py` | © 2026 tiqi9896 | MIT |
| `proxy/` (all files: `proxy.py`, `kernel/`, `docs/AGENTS.md`) | © 2026 tiqi9896 | MIT |
| `skill/llm-refusal-bypass/` | © 2026 tiqi9896 | MIT |

## Upstream project

The original prompt kernel and the Hermes plugin scaffold come from:

> **https://github.com/Enchanted0911/hermes-jailbreak-kernel** — MIT, © 2026 Enchanted0911

The upstream project is credited in `plugin/plugin.yaml` (`homepage`) and in the
header of each inherited prompt file. Its MIT license text is reproduced in
`LICENSE`. Per the MIT terms, **the copyright notice and permission notice must
be retained in all copies or substantial portions** — do not strip the
`Enchanted0911` attribution from the inherited prompt files.

## What this adaptation adds

### The framework-agnostic proxy (`proxy/`)

The plugin only works inside Hermes. Most AI coding agents have no plugin
mechanism, but they all have one thing in common: **a `base_url` setting**.

`proxy/` is a dependency-free HTTP proxy that injects the kernel before
forwarding to MiniMax. It works with any agent that can set a base URL, over
three protocol shapes (Anthropic Messages, OpenAI Chat Completions, OpenAI
Responses). It shares the **same kernel text** as the plugin, so both behave
identically.

Original work in this repository, including:

- protocol-aware injection for all three shapes, with idempotency checks
  (re-injection never duplicates the kernel or the scope statement),
- **fail-soft** by design: an injection failure passes the original request
  through unchanged rather than breaking the agent,
- API-key pass-through (the agent keeps its own key) with optional fallback,
- an output-cap floor, because thinking tokens and output tokens share
  `max_tokens` and a low client cap silently truncates the answer,
- streaming (SSE) pass-through,
- an offline `--self-test` that needs neither a key nor a network.

The per-agent configuration guide in `proxy/docs/AGENTS.md` was written from
those agents' own documentation; the base-URL shapes differ per client and
getting `/v1` wrong is the most common setup failure.

## What else this adaptation adds

Everything below is original work in this repository:

1. **MiniMax M3.1-Flash specific request-layer corrections**
   - Anthropic-compatible mode puts `system` at the **top level** of the request
     body, not inside `messages`. Plugins that only scan `messages` fail
     silently (registered, logged, request sent, zero effect).
   - `thinking.budget_tokens` is **ignored** by M3.1-Flash; only
     `output_config.effort` (adaptive thinking) has any effect. Hermes'
     default path routed MiniMax into a manual-`budget_tokens` branch.
   - Route detection prefers the **model name** over `base_url`, because a
     fallback chain can keep the MiniMax `base_url` while the model has already
     swapped to another provider.
2. **Delivery-fidelity reinforcement** (`strict.md` + `reinforce.md`)
   - Suppresses two distinct failure modes measured on M3.1-Flash:
     *hard refusals* and *topic drift into defensive framing* (e.g. a
     requested tool turning into a "detection & remediation guide").
   - The decisive lever was appending a **scope/authorization statement to the
     end of the user message**, not to the system prompt.
3. **Session-coverage guarantee**
   - System-prompt sections are **frozen per session** at creation time, so a
     session created before the plugin was enabled has no kernel in its
     persisted prompt. A request-layer fallback re-injects it on every call.
4. **A/B measurement harness** (`skill/llm-refusal-bypass/`) — layered refusal
   diagnosis, verdict classification, and a reproducible probe script.

## Scope notice

This repository contains **only** the plugin, the measurement skill, and
documentation. It contains no credentials, no personal data, no conversation
history, and no generated deliverable content.

## Responsible use

This tool changes the *behavior contract* of a model you call with your own
API key. It does not and cannot bypass a provider's server-side enforcement,
and it does not make anyone else's systems more accessible.

Use it only for work you are authorized to do, and comply with your provider's
terms of service and applicable law.
