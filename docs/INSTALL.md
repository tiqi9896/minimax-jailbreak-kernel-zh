# 安装指南


**语言 / Language**：**中文**（本文） | [English](INSTALL.en.md)

## 环境要求

- Hermes Agent `>= 0.19`（插件用到 `register_middleware("llm_request", ...)`
  和 `register_system_prompt_section(...)`）
- Python 3.10+（在 `from __future__ import annotations` 下使用 `X | None` 类型语法）
- 一个 MiniMax API key（真实调用模型时需要；插件本身永远不需要）

## 1. 拿到插件

```bash
git clone https://github.com/tiqi9896/minimax-jailbreak-kernel-zh.git
cd minimax-jailbreak-kernel
```

或下载压缩包解压。

## 2. 拷进你的 Hermes 插件目录

插件就是一个目录。Hermes 从 `~/.hermes/plugins/` 加载插件
（确切路径取决于你的安装方式；查 `hermes plugins list` 的输出或 `HERMES_HOME`）。

```bash
# Linux / macOS
cp -r plugin ~/.hermes/plugins/minimax-jailbreak-core

# Windows PowerShell
Copy-Item -Recurse .\plugin "$env:USERPROFILE\.hermes\plugins\minimax-jailbreak-core"
```

最终目录结构必须是 `.../plugins/minimax-jailbreak-core/__init__.py`，
旁边有 `prompts/profiles/`。

## 3. 启用它

```bash
hermes plugins enable minimax-jailbreak-core
```

`hermes plugins list` 现在应该显示 `minimax-jailbreak-core` 为 **enabled**。
这是**热加载** —— 你不需要重启 gateway。

> 如果你还装了上游的 `hermes-jailbreak-kernel`，**把它关掉** ——
> 两个同时跑会往同一个 system prompt 里注入两份不同的内核，结果不可预测：
> ```bash
> hermes plugins disable hermes-jailbreak-kernel
> ```

## 4. 让 Hermes 用 MiniMax M3.1-Flash

在 `~/.hermes/config.yaml`：

```yaml
model:
  default: MiniMax-M3.1-Flash
  provider: minimax-cn
  base_url: https://api.minimaxi.com/anthropic
```

并设置 key（插件自己不读 key —— Hermes 读）：

```bash
export MINIMAX_CN_API_KEY=<your key>
```

## 5. 验证

```bash
cd ~/.hermes/plugins/minimax-jailbreak-core
python selftest.py
```

预期输出类似：`结果: 17 通过, 0 失败`。

这个测试**完全离线** —— 它用合成的请求载荷驱动中间件，从不联系模型。

然后确认插件在真实请求路径上确实生效：

```bash
grep "minimax-jailbreak-core" ~/.hermes/logs/gateway.log | tail
```

你应该看到类似：

```
minimax-jailbreak-core: thinking->adaptive effort=medium
```

## 6. 确认行为真的变了

自测证明插件能正确改写请求。要证明**模型**行为变了，跑活体探针（需要你的 key）：

```bash
python ~/.hermes/skills/llm-refusal-bypass/scripts/refusal-probe.py \
  --key-env MINIMAX_CN_API_KEY \
  --base-url https://api.minimaxi.com/anthropic/v1/messages \
  --model MiniMax-M3.1-Flash \
  --effort medium
```

插件**开着**和**关着**各跑一次，对比 verdict 计数 ——
**这个 A/B 才是唯一能证明改动是真的东西**。见 [`USAGE.en.md`](USAGE.en.md)。

## 可选：安装测量技能

```bash
cp -r skill/llm-refusal-bypass ~/.hermes/skills/
```

这个技能讲的是**任何**托管模型的分层诊断和 verdict 分类方法，不只 MiniMax。

## 疑难排查

| 现象 | 原因 | 解法 |
|---|---|---|
| 插件显示 enabled 但行为没变 | Hermes 构造请求时没有顶层 `system`（走了 OpenAI 兼容路由） | 确认 `base_url` 是 Anthropic 兼容端点，或 `api_mode` 是 `anthropic_messages` |
| 空回复，`stop_reason=max_tokens` | 思考吃光了输出预算 | 抬 `max_tokens`，或降 `effort` |
| 插件注册了但日志看不到效果 | 上游插件和本插件同时启用 | `hermes plugins disable hermes-jailbreak-kernel` |
| 加载时 `ImportError` | 插件多拷了一层目录 | `__init__.py` 必须直接放在插件目录里 |
| 老会话仍然软化 | 会话早于插件启用 | 不用管 —— 请求层兜底会覆盖它；确认 `HERMES_JAILBREAK_BOOTSTRAP` 不是 `0` |
| 标题漂成防守方措辞 | 内核没生效 | 查 `gateway.log` 里有没有 `auth block appended`；改插件源码后必须热重载 |

## 代理方式（跨生态，20+ agent 通用）

不想装插件、或者用的是别的 agent，走代理：

```bash
bash install.sh              # macOS / Linux / Git Bash
.\install.ps1                # Windows PowerShell
```

安装脚本会装到 `~/.hermes/jailbreak-proxy/` 并建一个开机自启。
验证：

```bash
curl http://127.0.0.1:8790/health
# {"status":"ok","profile":"strict","effort":"medium"}
```

然后把你 agent 的 `base_url` 指过去（OpenAI 兼容用 `/v1`，Anthropic 兼容用 `/anthropic`）。
逐个 agent 的配置见 [`../proxy/docs/AGENT-SETUP.md`](../proxy/docs/AGENT-SETUP.md)（本文件即中文版）。
