# Contributing


**Language:** English | [Chinese (zh-CN)](CONTRIBUTING.md)

Thanks for considering a contribution. This project is small and the bar for
a useful PR is low: **a change that is measured, and a claim you can
reproduce.**

## Ground rules

1. **Measure before you claim.** A PR that says "this makes the model comply
   more" without numbers will be asked for numbers. The bundled
   `skill/llm-refusal-bypass/` exists for exactly this — use it.
2. **One variable at a time.** If you change the kernel text *and* the effort
   setting, nobody can tell which one moved the result.
3. **Report the control group.** Experimental numbers alone are not evidence.
4. **Don't touch unrelated files.** The plugin is one directory plus one skill.
4b. **Never hardcode absolute paths.** Use `Path(__file__).resolve().parent`
   and environment variables. See "Portable paths" below.
5. **Never commit secrets.** No API keys, no `.env`, no `state.db`, no logs.
   The `.gitignore` already covers the common cases — check before adding.

## Portable paths — the trap we actually fell into

The kernel text lookup originally pointed at a hardcoded absolute path to the
upstream plugin. Two problems:

- Anyone who cloned this repo got a `TypeError` / `FileNotFoundError` unless
  they happened to have the upstream plugin installed at the same absolute
  path on their machine.
- It leaks the original author's directory layout.

The fix is a three-tier probe:

```python
def _detect_upstream_profiles() -> Path | None:
    env = os.environ.get("HERMES_JAILBREAK_UPSTREAM_PROFILES", "").strip()
    if env and Path(env).is_dir():
        return Path(env)
    sibling = Path(__file__).resolve().parent.parent / "hermes-jailbreak-kernel" / "prompts" / "profiles"
    if sibling.is_dir():
        return sibling
    return None
```

**And the second trap:** any function that does `root / filename` must guard
against `root is None`. Otherwise the plugin works on the author's machine
(the upstream *is* installed there, so the probe never returns `None`) and
crashes for every other user.

### Required check before you open a PR

```bash
# Copy the plugin somewhere with no sibling upstream plugin, then run the test:
cp -r plugin /tmp/standalone/minimax-jailbreak-core
cd /tmp/standalone/minimax-jailbreak-core && python selftest.py
```

Expected: a summary line reporting **17 passed, 0 failed** (the tool prints
its summary in Chinese).

If that passes only on your machine and not in a clean directory, you have the
`None` bug.

## Working on the proxy

`proxy/` is a standalone HTTP proxy. It has its own offline test suite:

```bash
cd proxy && python proxy.py --self-test
```

It must keep two properties:

1. **Fail-soft.** If injection raises for any reason, the original request
   must be forwarded unchanged. A proxy that breaks the agent is worse than
   no proxy. Never let an exception escape into the request path.
2. **Idempotent.** The agent may retry, or the same body may pass through
   twice. The kernel and the scope statement must never be duplicated.
   Both injection paths check for their marker before appending.

When you add a protocol shape, mirror the existing three:
per-shape injection function, a path suffix check in the router, and
self-test cases that assert (a) the kernel landed, (b) the original
content survived, (c) a second injection does not duplicate anything.

### The `/v1` trap

Clients disagree about whether the base URL ends in `/v1`:

- clients that append `/chat/completions` → base URL **with** `/v1`
- clients that append `/v1/messages` → base URL **without** `/v1`

The proxy accepts both for the Anthropic shape (it matches on the path
suffix, not on the base URL). Keep it that way, and document the exact
value for each agent in `proxy/docs/AGENT-SETUP.md`.

### The output-cap floor

Thinking tokens and output tokens share `max_tokens`. A client that sets a
low cap (4096 / 8000) gets a **truncated** answer that looks like a
failure — the upstream reports `status=incomplete,
reason=max_output_tokens`. The proxy raises the floor to
`--min-output-tokens` (default 16000) and logs when it does. If you change
the default, say why in the commit message.

## Running the tests

```bash
# offline, no API key, no network
cd plugin && python selftest.py
```

The self-test exercises the middleware against synthetic request payloads:
system-prompt rebuilding, effort injection, the auth block, the per-session
bootstrap fallback, route detection, and fail-soft behavior on malformed
input.

## Live testing (needs your own key)

```bash
python skill/llm-refusal-bypass/scripts/refusal-probe.py \
  --key-env MINIMAX_CN_API_KEY \
  --base-url https://api.minimaxi.com/anthropic/v1/messages \
  --model MiniMax-M3.1-Flash \
  --effort medium
```

Run it with the plugin enabled and disabled and compare the verdict counts.
That A/B is the only thing that proves the change is real.

**Mind the quota.** Large-budget regression runs will exhaust a metered plan.
Serialize your runs, use layered budgets, and stop on a quota error — do not
let 429s contaminate your refusal statistics.

## Style

- Keep the kernel prompt text in `prompts/profiles/*.md`, not inline in Python.
- The kernel ships as **two segments** with different jobs:
  - the *main contract* — what to do
  - the *reinforcement* — how it must not be silently downgraded

  Do not merge them into one blob; measurably weaker. Keep the combined size
  under the provider's per-section budget.
- Comment the **why**, not the what. Especially for the request-layer quirks
  (top-level `system`, ignored `budget_tokens`, model-name-first route
  detection) — those look like nonsense without context.
- Match the surrounding style: bilingual comments are fine, the upstream
  prompt corpus is bilingual.

## Adding a profile

1. Create `prompts/profiles/<name>.md`.
2. Register it in `PROFILE_FILES` and in `SECTION_SPLIT` (which segment file
   pairs with it).
3. Add a self-test case.
4. Document it in the README's profile list.

## Adding an environment variable

1. Read it through the existing `_truthy` / `_falsey` helpers so that
   `1`/`true`/`yes`/`on` and `0`/`false`/`no`/`off` all behave.
2. Give it a default and document it in the README's environment table.
3. Add a self-test case that sets and removes it.

## Attribution

The prompt corpus in `plugin/prompts/profiles/{core,research,creative,max}.md`
is MIT-inherited verbatim from
[Enchanted0911/hermes-jailbreak-kernel](https://github.com/Enchanted0911/hermes-jailbreak-kernel)
(© 2026 Enchanted0911).

**Do not remove or reword that attribution.** If you add a new prompt file,
say in `NOTICE` which parts are yours and which are inherited.

## Reporting issues

Please include:

- the exact model id and effort setting,
- the plugin version (from `plugin/plugin.yaml`),
- the verdict classification you observed (`COMPLY` / `SOFT-REFUSE` /
  `HARD-REFUSE` / `TRUNCATED` / `COMPLY(tool_use)`),
- the relevant response fields: `stop_reason`, body length, and
  `thinking_tokens`.

The `thinking_tokens` field matters: an empty body with
`stop_reason=max_tokens` is a **thinking-budget exhaustion**, not a refusal,
and no prompt change will fix it.

## Scope

This project changes how a model behaves toward requests made with **your**
API key. It does not defeat provider-side enforcement and it does not make
anyone else's systems more accessible. Contributions should stay within that
framing — please don't add features aimed at third-party systems.
