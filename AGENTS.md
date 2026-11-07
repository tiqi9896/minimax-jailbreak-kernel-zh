# AGENTS.md（中文版）

**语言 / Language**：**中文**（本文） | [English](AGENTS.en.md)

> **如果你是正在读这个文件的 AI agent：** 本仓库为 **MiniMax M3.1-Flash**
> （`MiniMax-M3.1-Flash`）安装一层「不拒答交付层」。
> 照着下面的步骤做。它们是自洽的 —— 你不需要问用户任何问题，
> 也不需要任何外部文档。


---

## 这是干什么的

用户用**自己的** API key 调 MiniMax M3.1-Flash，结果拿到的是拒答、免责话术、
被软化的交付物，或者被截断的输出。本仓库加一层**提示词级交付契约**来修这个，
**全程不碰服务商**。

原理是：把内核注入到发往 MiniMax 之前的请求里。两种载体：

| 载体 | 什么时候用 |
|---|---|
| **`proxy/proxy.py`** | **默认选它。** 任何能设 `base_url` 的 agent 都能用，不需要 agent 侧插件。 |
| `plugin/` | 用户跑的是 Hermes Agent，且想要原生路径（会话级开关）。 |

**几乎所有情况都该用代理。** 除非用户明确说他跑 Hermes Agent 且要插件，
否则一律用代理。

---

## 第 1 步 —— clone

```bash
git clone https://github.com/tiqi9896/minimax-jailbreak-kernel-zh.git
cd minimax-jailbreak-kernel
```

## 第 2 步 —— 验证安装（离线，不要 API key，不联网）

```bash
python proxy/proxy.py --self-test
```

预期输出**最后一行**是这个（中文和英文写在同一行）：

```
ALL PASSED / 结果: 全部通过
```

两种语言写在同一行是故意的 —— 读中文文档的 agent 和读英文文档的 agent
拿到的是同一个标记。

如果这行没有（或者写的是 `SELF-TEST FAILED / 自检失败`），
**把失败原文照报给用户并停下** —— 不要去「修」内核文案。

> 自测里现在包含一次**真实的端到端 HTTP 往返**：起一个本地桩上游，
> 对三种协议形状各发一个真请求，断言拿得到响应。
> 这一段能抓住「代理能启动、但每个请求都死」——
> 只测函数的测试看不出这种故障。

> Windows 上 `python` 可能是 `py -3` 或 `python3`。找不到 `python` 就试另外两个。
> 代理需要 **Python 3.9+，且只需要这个** —— 没有 `pip install`，没有虚拟环境，没有依赖。

## 第 3 步 —— 启动代理

```bash
python proxy/proxy.py --verbose
```

它监听 `http://127.0.0.1:8790`。**让它一直跑着。**

后台运行：

```bash
# macOS / Linux
nohup python proxy/proxy.py --verbose > /tmp/minimax-jailbreak-proxy.log 2>&1 &

# Windows (PowerShell)
Start-Process python -ArgumentList "proxy/proxy.py","--verbose" -WindowStyle Hidden
```

你可能用得上的选项：

| 选项 | 默认 | 什么时候用 |
|---|---|---|
| `--port` | `8790` | 端口被占 |
| `--host` | `127.0.0.1` | 除非用户另有要求，保持只监听本机 |
| `--api-key-env` | — | agent 自己发不出 key 时 |
| `--profile` | `strict` | `strict` / `core` / `max` / `research` / `creative` |
| `--effort` | `medium` | `low` / `medium` / `high` / `xhigh` / `max` |
| `--min-output-tokens` | `16000` | `0` 表示取消输出下限 |
| `--verbose` | 关 | 打开以看到逐请求的注入状态 |

## 第 4 步 —— 把用户的 agent 指向代理

模型 id 是 **`MiniMax-M3.1-Flash`**（2026-10-19 发布的正式版）。
**不是** `MiniMax-M3.1-Flash-Preview` —— 那是更早的 preview id。

| agent 说的是 | base URL 设成 |
|---|---|
| OpenAI Chat Completions | `http://127.0.0.1:8790/v1` |
| Anthropic Messages | `http://127.0.0.1:8790/anthropic` |
| OpenAI Responses | `http://127.0.0.1:8790/v1`（会路由到 `/v1/responses`） |

**20+ 个 agent 的逐个配置** —— Claude Code、OpenCode、OpenClaw、
Cursor、Qoder、Cline、Roo Code、Kilo Code、Continue、Aider、Goose、Zed、
Factory Droid、Codex CLI、Hermes Agent、WorkBuddy、Devin —— 在
[`proxy/docs/AGENT-SETUP.md`](proxy/docs/AGENT-SETUP.md)（本文件即中文版）
（英文版 `AGENT-SETUP.md`）。**读那个文件，套用用户那个 agent 的小节。**

两个导致大部分安装失败的坑：

1. **`/v1` 后缀取决于客户端。** 客户端自己会拼 `/chat/completions` 的，
   base URL 要**带** `/v1`；客户端自己会拼 `/v1/messages` 的
   （Claude Code、Zed 的 `anthropic_compatible`、Goose），base URL 要**不带** `/v1`。
   agent-setup 文档里逐个写明了。代理两种 Anthropic 形式都接受。
2. **Cursor 和 Codex CLI 只接受公网 HTTPS 端点** —— 它们的 BYOK 请求从
   *它们自己的*服务器发出，不是从用户机器。`localhost` URL 到不了它们，
   用户需要隧道（ngrok / cloudflared）。**如果用户的 agent 是这两个之一，
   一定要明确告诉他** —— 否则他会去 debug 错误的方向。

API key：代理**透传 agent 发过来的 key**。用户继续在原本的 agent 设置里用他
平时的 MiniMax key。除非 agent 发不出 key（那就用 `--api-key-env`），
否则不要把 key 搬进代理。

## 第 5 步 —— 确认真的生效

让用户给一个他 agent 平时会拒的请求，然后对比：

- **经代理**：完整交付物
- **不经代理**（临时把 agent 指回上游）：拒答

开着 `--verbose` 时，代理每个请求打印一行：

```
[proxy] openai status=200 kernel=Y auth=Y effort=medium floor=16000 13.2s
```

- `kernel=Y` → 内核已注入
- `auth=Y` → 范围声明已追加到 user 消息
- `status=200` → 上游健康

如果 `kernel=n`，说明请求绕过了代理 —— base URL 填错了。

**没做这一步检查就不要声称成功。** 代理自己的 `--self-test` 只证明注入逻辑对；
只有真实往返才能证明模型行为变了。

### 如果客户端报「连接被关闭」/`RemoteDisconnected`

对**正在跑的**代理跑一遍附带的冒烟脚本：

```bash
python tests/proxy_smoke.py --port 8790
```

它把三种在客户端看来一模一样的故障区分开：

| 冒烟脚本的输出 | 含义 |
|---|---|
| `/health` 连不上 | 代理没在跑 / 端口不对 |
| `/health` 正常，然后 `RemoteDisconnected` | **代理处理请求时崩了** —— 跑 `python proxy/proxy.py --self-test`，端到端检查项会指出原因 |
| 401 | key 没到位 —— agent 必须自己带 key |

拿到 401 本身就说明请求路径是活的。

---

## 改用 Hermes 插件

只有当用户跑 Hermes Agent 且明确要走原生插件路径时：

```bash
cp -r plugin ~/.hermes/plugins/minimax-jailbreak-core
hermes plugins enable minimax-jailbreak-core
cd ~/.hermes/plugins/minimax-jailbreak-core && python selftest.py
```

预期：`结果: 17 通过, 0 失败`（离线，不需要 key）。

插件额外提供会话级控制：

```
/jailbreak on|off|slim|full
profile core|strict|max|research|creative
effort low|medium|high|max
```

**两种载体共用同一份内核文案**，所以行为一致。

---

## 仓库结构

```
proxy/proxy.py              代理本体 —— 纯标准库，无依赖
proxy/kernel/               内核文案（两段）
proxy/docs/AGENT-SETUP.md   20+ agent 逐个配置（英文）
proxy/docs/AGENT-SETUP.zh-CN.md  同上（中文）
plugin/minimax-jailbreak-core/   Hermes 原生插件
skill/llm-refusal-bypass/   测量方法论 + 探针脚本
tests/                      可移植验收脚本（标题专项 / 多轮交付率）
docs/                       安装 / 使用说明（INSTALL.zh-CN.md、USAGE.zh-CN.md）
```

## 你需要知道的事实（在 MiniMax-M3.1-Flash 上实测，不是猜的）

- 这个模型**忽略** `thinking.budget_tokens` —— 只有
  `output_config.effort`（adaptive thinking）有效。
- **空正文通常不是拒答** —— 是思考预算吃光 `max_tokens`。
  查 `status=incomplete` / `reason=max_output_tokens` 并抬高上限。
  代理把下限抬到 16000 正是为此。
- 拒答发生在**模型行为层**、不是服务端，所以提示词层契约能压制它。
- `effort=medium` 是最佳档。
- 决定性杠杆是 **user 消息末尾的范围声明**，不是 system prompt。
- 残余失败形态是**靠删掉动作来降级**（例如把要的工具交付成只读扫描器）。
  内核的降级清单专门针对它。
- `MiniMax-M3`（非 Flash 版）需要 `max_tokens` ≥ 32000；它思考重得多。

## 疑难排查

| 现象 | 原因 | 解法 |
|---|---|---|
| 没有 `结果: 全部通过` | Python 太旧 / 找不到 | 试 `python3`、`py -3`；需要 3.9+ |
| 404 / model not found | base URL 的 `/v1` 对该客户端不对 | 查 `proxy/docs/AGENT-SETUP.md` 里该 agent 那节 |
| 401 invalid API key | agent 自己的 key 没到 MiniMax | 检查 agent 的 key 设置；代理不存 key |
| connection refused | 代理没在跑 | 启动它；确认 `--port` 和 base URL 一致 |
| 什么都没变 | agent 没走代理 | 在代理日志里找 `kernel=n` |
| Cursor/Codex 连不上 | 它们要公网 HTTPS 端点 | 配隧道 |
| 回答被截一半 | 输出上限太低 | 抬 `--min-output-tokens` |

## 给 agent 你的规则

- **绝不要为了让「能用」去改内核文案。** 某个用例失败就带着响应正文报出来；
  内核是调过的，改它需要走 `skill/llm-refusal-bypass/` 里的测量闭环。
- **给本仓库加代码时绝不要硬编码绝对路径。** 用
  `Path(__file__).resolve().parent`。CONTRIBUTING 里有关于这条的规则，
  而且它真的造成过 bug。
- **没做第 5 步的往返检查，就不要声称配置成功。**
- 代理默认绑 `127.0.0.1`，且**没有鉴权**。如果用户想用隧道暴露出去，
  提醒他们**先在前面加认证**。
- 范围说明：这改变的是模型对**用用户自己的 key** 发出的请求的行为。
  它不击穿服务商侧审核，也不会让第三方系统更容易被访问。
  工作范围请留在用户已获授权的边界内。

## 更多细节

- [`docs/INSTALL.en.md`](docs/INSTALL.en.md) —— 安装 + 验证细节
- [`docs/USAGE.en.md`](docs/USAGE.en.md) —— A/B 测量方法论
- [`proxy/docs/AGENT-SETUP.md`](proxy/docs/AGENT-SETUP.md)（本文件即中文版） —— 逐个 agent 配置
- [`CONTRIBUTING.en.md`](CONTRIBUTING.en.md) —— 怎样贡献而不破坏可移植性
