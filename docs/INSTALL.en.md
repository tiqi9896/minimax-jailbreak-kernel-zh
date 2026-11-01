# Install


**Language:** English | [Chinese (zh-CN)](INSTALL.md)

## Requirements

- Hermes Agent `>= 0.19` (the plugin uses `register_middleware("llm_request", ...)`
  and `register_system_prompt_section(...)`)
- Python 3.10+ (uses `X | None` type syntax under `from __future__ import annotations`)
- A MiniMax API key, for actual model calls (the plugin itself never needs one)

## 1. Get the plugin

```bash
git clone https://github.com/tiqi9896/minimax-jailbreak-kernel-zh.git
cd minimax-jailbreak-kernel
```

Or download the archive and extract it.

## 2. Copy it into your Hermes plugins directory

The plugin is a single directory. Hermes loads plugins from `~/.hermes/plugins/`
(the exact path depends on your install; check `hermes plugins list` output or
`HERMES_HOME`).

```bash
# Linux / macOS
cp -r plugin/minimax-jailbreak-core ~/.hermes/plugins/

# Windows PowerShell
Copy-Item -Recurse .\plugin\minimax-jailbreak-core "$env:USERPROFILE\.hermes\plugins\"
```

The directory must end up as `.../plugins/minimax-jailbreak-core/__init__.py`
with `prompts/profiles/` next to it.

## 3. Enable it

```bash
hermes plugins enable minimax-jailbreak-core
```

`hermes plugins list` should now show `minimax-jailbreak-core` as **enabled**.
This hot-reloads — you do not need to restart the gateway.

> If you also have `hermes-jailbreak-kernel` (the upstream project) installed,
> **disable it** — running both injects two different kernels into the same
> system prompt and the result is unpredictable:
> ```bash
> hermes plugins disable hermes-jailbreak-kernel
> ```

## 4. Point Hermes at MiniMax M3.1-Flash

In `~/.hermes/config.yaml`:

```yaml
model:
  default: MiniMax-M3.1-Flash
  provider: minimax-cn
  base_url: https://api.minimaxi.com/anthropic
```

And set the key (the plugin does not read the key itself — Hermes does):

```bash
export MINIMAX_CN_API_KEY=<your key>
```

## 5. Verify

```bash
cd ~/.hermes/plugins/minimax-jailbreak-core
python selftest.py
```

Expected: a summary line reporting **99 passed, 0 failed** (the tool prints
its summary in Chinese).

This test is **fully offline** — it exercises the middleware against synthetic
request payloads and never contacts a model.

Then confirm the plugin is live in the real request path:

```bash
grep "minimax-jailbreak-core" ~/.hermes/logs/gateway.log | tail
```

You should see lines like:

```
minimax-jailbreak-core: thinking->adaptive effort=medium
```

## 6. Confirm the behavior actually changed

The self-test proves the plugin transforms requests correctly. To prove the
*model* behaves differently, run the live probe (needs your key):

```bash
python ~/.hermes/skills/llm-refusal-bypass/scripts/refusal-probe.py \
  --key-env MINIMAX_CN_API_KEY \
  --base-url https://api.minimaxi.com/anthropic/v1/messages \
  --model MiniMax-M3.1-Flash \
  --effort medium
```

Run it with the plugin **enabled** and **disabled** and compare the verdict
counts — that A/B is the only thing that proves the change is real. See
`docs/USAGE.md`.

## Optional: install the measurement skill

```bash
cp -r skill/llm-refusal-bypass ~/.hermes/skills/
```

The skill teaches the layered diagnosis and verdict classification for any
hosted model, not just MiniMax.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Plugin shows as enabled but nothing changes | Hermes built the request without a top-level `system` (OpenAI-compatible route) | Confirm `base_url` is the Anthropic-compatible endpoint, or that `api_mode` is `anthropic_messages` |
| Empty reply, `stop_reason=max_tokens` | Thinking ate the whole output budget | Raise `max_tokens`, or lower `effort` |
| Plugin registers but logs show no effect | Upstream and this plugin both enabled | `hermes plugins disable hermes-jailbreak-kernel` |
| `ImportError` on load | Plugin copied one level too deep | `__init__.py` must sit directly in the plugin directory |
| Old session still softens | Session predates the plugin | Nothing to do — the request-layer fallback covers it; confirm `HERMES_JAILBREAK_BOOTSTRAP` is not `0` |
