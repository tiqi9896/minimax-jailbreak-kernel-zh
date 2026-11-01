# Connecting any AI agent to the delivery proxy

> **This is the English edition.** Per-agent base_url configuration, protocol traps, and
> verification. The Chinese edition of this file is [`AGENT-SETUP.md`](AGENT-SETUP.md).

The delivery proxy is **framework-agnostic**: it works at the HTTP layer, so any agent
that can change a `base_url` can use it — no plugin to install, not a single line of
agent-side code to change.

```
your agent  ──►  http://127.0.0.1:8790/...  ──►  delivery proxy  ──►  api.minimaxi.com
                   (injects the kernel)              (forwards unchanged)
```

---

## 1. Start the proxy

```bash
python proxy.py                 # listen on 127.0.0.1:8790
python proxy.py --port 9000     # different port
python proxy.py --verbose       # print a per-request injection summary
python proxy.py --self-test     # offline self-test, no network requests
```

By default the proxy **passes your own API key through** (you never hand the key to the
proxy for safekeeping). To give it a fallback instead:
`python proxy.py --api-key-env MINIMAX_API_KEY`.

## 2. Two base_urls — pick by the agent's protocol habit

| The agent speaks | Set this base_url |
|---|---|
| OpenAI-compatible (Chat Completions) | `http://127.0.0.1:8790/v1` |
| Anthropic-compatible (Messages) | `http://127.0.0.1:8790/anthropic` |
| OpenAI Responses (Codex CLI, …) | `http://127.0.0.1:8790/v1` (routes to `/v1/responses`) |

The proxy **supports all three** and detects the shape from the request path — you never
need a second port per agent.

**Whether `/v1` belongs in the base URL depends on whether the client appends its own
suffix** — this is the single most common setup failure:

- clients that append `/chat/completions` or `/v1/messages` themselves ⇒ **include `/v1`**,
  or follow the per-agent notes below
- clients that append `/v1/messages` themselves (Claude Code and friends) ⇒ **omit `/v1`**

Both Anthropic spellings are accepted:

- `http://127.0.0.1:8790/anthropic` → the proxy appends `/v1/messages`
- `http://127.0.0.1:8790/anthropic/v1` → the client appends `/messages`; the proxy still
  recognises it

Model id is always **`MiniMax-M3.1-Flash`** (the GA id released 2026-10-19).

### ★ The output cap is raised automatically

Thinking tokens and output tokens **share** `max_tokens`. If a client sets the cap to
4096 / 8000, the model spends ~7000 on thinking and the body gets truncated
(the upstream reports `status=incomplete, reason=max_output_tokens`) — **it looks like a
failure, but half the answer is actually there**.

The proxy raises the output cap to **16000** (`--min-output-tokens`) and logs
`floor=16000` so you know it intervened. Pass `--min-output-tokens 0` to disable that.

---

## 3. Per-agent configuration

### Claude Code

Environment variables (`ANTHROPIC_BASE_URL` **without `/v1`** — Claude Code appends
`/v1/messages` itself):

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8790/anthropic"
export ANTHROPIC_AUTH_TOKEN="$MINIMAX_API_KEY"     # sent as Authorization: Bearer sent as
export ANTHROPIC_MODEL="MiniMax-M3.1-Flash"
```

★ Claude Code's aliases and background calls ask for its own Claude model ids — set the
`ANTHROPIC_DEFAULT_*_MODEL` family as well.

### OpenCode

`opencode.json` (project root or `~/.config/opencode/opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "minimax": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "MiniMax (via jailbreak proxy)",
      "options": {
        "baseURL": "http://127.0.0.1:8790/v1",
        "apiKey": "{env:MINIMAX_API_KEY}"
      },
      "models": {
        "MiniMax-M3.1-Flash": {
          "name": "MiniMax M3.1 Flash",
          "limit": { "context": 1000000, "output": 131072 }
        }
      }
    }
  },
  "model": "minimax/MiniMax-M3.1-Flash"
}
```

For the Anthropic-compatible variant, swap `"npm"` for `"@ai-sdk/anthropic"` and use
`"http://127.0.0.1:8790/anthropic/v1"` as `baseURL` (**this package needs `/v1`** — the
opposite of Claude Code).

### OpenClaw

`~/.openclaw/openclaw.json`:

```json
{
  "agents": { "defaults": { "model": { "primary": "minimax/MiniMax-M3.1-Flash" } } },
  "models": {
    "mode": "merge",
    "providers": {
      "minimax": {
        "baseUrl": "http://127.0.0.1:8790/v1",
        "apiKey": "${MINIMAX_API_KEY}",
        "api": "openai-completions",
        "models": [
          {
            "id": "MiniMax-M3.1-Flash",
            "name": "MiniMax M3.1 Flash",
            "reasoning": true,
            "input": ["text", "image"],
            "contextWindow": 1000000,
            "maxTokens": 131072
          }
        ]
      }
    }
  }
}
```

### Cursor

**Settings → Models** (in Cursor):

1. Turn on **Override OpenAI Base URL** and set `http://127.0.0.1:8790/v1`
2. Put your MiniMax key in **API Key** and enable "Use OpenAI API key"
3. **Add model**, name it `MiniMax-M3.1-Flash`, and enable it

★ **Cursor has two hard limits — read them first**:
- **BYOK requests go through Cursor's own servers**, so a `localhost` URL will not reach
  them — you need a public tunnel (ngrok / cloudflared) that exposes the proxy as a public
  HTTPS endpoint. **Cursor only accepts a public HTTPS endpoint.**
- Once the override is on, **Cursor's own models also go through that endpoint** and fail.
  Turn the override off when you want to use Cursor's built-in models.
- Tab completion still uses Cursor's own models and is unaffected.

### Cline / Roo Code / Kilo Code

**Cline / Roo Code**: in the extension settings pick **OpenAI Compatible**, set Base URL
to `http://127.0.0.1:8790/v1`, API key to your MiniMax key, and Model ID to
`MiniMax-M3.1-Flash`.

Roo Code also accepts an imported settings JSON:

```json
{
  "providerProfiles": {
    "currentApiConfigName": "minimax-proxy",
    "apiConfigs": {
      "minimax-proxy": {
        "apiProvider": "openai",
        "openAiBaseUrl": "http://127.0.0.1:8790/v1",
        "openAiApiKey": "YOUR_MINIMAX_KEY",
        "openAiModelId": "MiniMax-M3.1-Flash",
        "openAiCustomModelInfo": {
          "contextWindow": 1000000,
          "maxTokens": 131072,
          "supportsImages": true,
          "supportsPromptCache": false
        }
      }
    }
  }
}
```

**Kilo Code** (`~/.config/kilo/kilo.json`):

```json
{
  "$schema": "https://app.kilo.ai/config.json",
  "model": "minimax/MiniMax-M3.1-Flash",
  "provider": {
    "minimax": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "MiniMax (via jailbreak proxy)",
      "options": {
        "baseURL": "http://127.0.0.1:8790/v1",
        "apiKey": "{env:MINIMAX_API_KEY}"
      },
      "models": {
        "MiniMax-M3.1-Flash": {
          "name": "MiniMax M3.1 Flash",
          "tool_call": true,
          "limit": { "context": 1000000, "output": 131072 }
        }
      }
    }
  }
}
```

### Continue

`~/.continue/config.yaml`:

```yaml
name: MiniMax via proxy
version: 0.0.1
schema: v1
models:
  - name: MiniMax M3.1 Flash
    provider: openai
    model: MiniMax-M3.1-Flash
    apiBase: http://127.0.0.1:8790/v1
    apiKey: ${{ secrets.MINIMAX_API_KEY }}
    roles: [chat, edit, apply]
    capabilities: [tool_use]
    defaultCompletionOptions:
      contextLength: 1000000
      maxTokens: 131072
```

### Aider

`.aider.conf.yml` (home dir / git root / cwd):

```yaml
model: openai/MiniMax-M3.1-Flash
openai-api-base: http://127.0.0.1:8790/v1
```

★ Aider needs an `openai/` prefix on the model id.

### Goose

`~/.config/goose/custom_providers/minimax.json`:

```json
{
  "name": "minimax",
  "engine": "openai",
  "display_name": "MiniMax (via jailbreak proxy)",
  "api_key_env": "MINIMAX_API_KEY",
  "base_url": "http://127.0.0.1:8790/v1",
  "models": [{ "name": "MiniMax-M3.1-Flash", "context_limit": 1000000 }],
  "supports_streaming": true,
  "requires_auth": true
}
```

### Zed

`settings.json` (in Zed):

```json
{
  "language_models": {
    "openai_compatible": {
      "minimax": {
        "api_url": "http://127.0.0.1:8790/v1",
        "available_models": [
          {
            "name": "MiniMax-M3.1-Flash",
            "display_name": "MiniMax M3.1 Flash",
            "max_tokens": 1000000,
            "max_output_tokens": 131072,
            "capabilities": { "tools": true, "images": true }
          }
        ]
      }
    },
    "anthropic_compatible": {
      "minimax-anthropic": {
        "api_url": "http://127.0.0.1:8790/anthropic",
        "available_models": [
          { "name": "MiniMax-M3.1-Flash", "max_tokens": 1000000, "max_output_tokens": 131072 }
        ]
      }
    }
  }
}
```

### Factory Droid

`~/.factory/settings.json`:

```json
{
  "customModels": [
    {
      "model": "MiniMax-M3.1-Flash",
      "displayName": "MiniMax M3.1 Flash (via proxy)",
      "baseUrl": "http://127.0.0.1:8790/v1",
      "apiKey": "${MINIMAX_API_KEY}",
      "provider": "generic-chat-completion-api",
      "maxOutputTokens": 131072
    }
  ]
}
```

### ★ Known weakness of the Responses path

OpenAI Responses (`/v1/responses`) is the **weakest** of the three paths: on the same
8-case suite it produced one soft refusal (the adult case opened with a soft refusal and
then wrote a non-explicit scene).

⇒ **If your agent can use the Anthropic or OpenAI-compatible path, prefer those.**
⇒ If the Responses path returns an empty or half-written body, check `status=incomplete`
   (`reason=max_output_tokens`) first — that is the output cap, not a refusal, and raising
   `--min-output-tokens` fixes it. Measured on the SQL-injection case: capped at 8000 it
   was truncated (reasoning 7060 + output 8000, with the title already correct); at the
   16000 floor it finished with `status=completed` and 10881 chars.

### Codex CLI

`~/.codex/config.toml`:

```toml
model = "MiniMax-M3.1-Flash"
model_provider = "minimax"

[model_providers.minimax]
name = "MiniMax (via jailbreak proxy)"
base_url = "http://127.0.0.1:8790/v1"
env_key = "MINIMAX_API_KEY"
wire_api = "responses"
```

★ Codex CLI only speaks the **Responses API** (`wire_api = "chat"` was removed). The
proxy supports `/v1/responses` (injecting `instructions` + `input`).
★ **But Codex only accepts a public HTTPS endpoint** — a local `127.0.0.1` will not reach
it, so you need a tunnel.

### Hermes Agent

`~/.hermes/config.yaml`:

```yaml
model:
  default: MiniMax-M3.1-Flash
  provider: minimax-cn
  base_url: http://127.0.0.1:8790/anthropic
```

> Hermes has a **native plugin** (this repo's `plugin/`) that is more complete than the
> proxy — it adds session-level on/off. If you run Hermes, prefer the plugin; the proxy is
> for every other agent.

### Qoder

In Qoder's settings pick **OpenAI Compatible / custom model**, set Base URL to
`http://127.0.0.1:8790/v1` and Model ID to `MiniMax-M3.1-Flash`.
(The menu wording differs slightly between versions; if you cannot find the OpenAI
Compatible option, running the local proxy and pointing the client's custom base_url at it
works just as well.)

### WorkBuddy

WorkBuddy speaks the OpenAI-compatible protocol — point its model service at:

```
Base URL:  http://127.0.0.1:8790/v1
API Key:   your MiniMax key
Model:     MiniMax-M3.1-Flash
```

### Cognition Devin

Devin's custom-model surface is narrow, and its requests usually originate from
Cognition's own servers (not from your machine), so **the local proxy does not apply**.
The workable alternative: deploy the proxy publicly (tunnel / VPS) and put that public
address on the Devin side.

---

## 4. Four classic failures and their fixes

| Symptom | Cause | Fix |
|---|---|---|
| 404 / model not found | the `/v1` in base_url is wrong for that client | see that agent's section above; OpenAI clients generally **need** `/v1` |
| 401 incorrect API key | the key is being overridden elsewhere | check saved login state, an old `OPENAI_BASE_URL`, the `env` block in settings |
| connection refused | the client only allows public HTTPS | set up a tunnel (Cursor / Codex explicitly require it) |
| goes through the proxy but **no effect** | the upstream is not MiniMax at all | the proxy logs `kernel=Y/N`; run with `--verbose` |
| Cursor's own models error | the override is on, so its own models are hijacked too | turn the override off when using Cursor's built-in models |

## 5. Confirm it actually works

The proxy is **observable**. Run it with `--verbose` and it prints one line per request:

```
[proxy] openai status=200 kernel=Y auth=Y effort=medium 13.2s
```

- `kernel=Y` ⇒ the kernel was injected
- `auth=Y` ⇒ the scope statement was appended to the user message
- `status=200` ⇒ the upstream is healthy

Then run `skill/llm-refusal-bypass/scripts/refusal-probe.py` once, or simply compare
"through the proxy" against "direct": a direct call to MiniMax refuses the same request
outright, while the proxied call delivers it in full. **That is the only reliable
acceptance method.**

## 6. Security note

The proxy listens on `127.0.0.1` by default — local machine only. If you expose it
through a tunnel, **put authentication in front of it** (a random path prefix, a header
check, …), otherwise anyone can spend your MiniMax key.
