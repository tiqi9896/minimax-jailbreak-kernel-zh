# 通用破甲代理（跨生态交付）

**当目标是「任何 AI agent 调用这个模型时都能生效」时，交付形态是本地 HTTP 代理，
不是框架插件。**

## 一、为什么代理是通用安装器

AI 编码 agent 没有统一的插件机制，但**都有 base_url**。
⇒ 代理在转发到上游之前改写请求 ⇒ 任何能改 base_url 的 client 都覆盖到。

```
客户端 ──► http://127.0.0.1:PORT/... ──► 代理（注入内核） ──► 上游 API
```

★ **代理与框架原生插件并存**：代理给万金油，原生插件给本框架
（多出会话级开关、上下文重建、per-session 兜底）。
**两者共用同一份内核文案** ⇒ 行为一致，不会一个能破一个不能。

## 二、三种协议形状与注入点

按**请求路径后缀**路由，不要按 base_url 路由（同一个 base 可能被不同客户端
再拼不同路径）。

| 协议 | 路径后缀 | system 注入点 | 用户内容注入点 | 思考参数 |
|---|---|---|---|---|
| Anthropic Messages | `/messages` | **顶层** `system`（字符串或 blocks 列表） | `messages[].content` | `output_config.effort` + `thinking.type=adaptive` |
| OpenAI Chat Completions | `/chat/completions` | `messages[]` 里 `role:"system"` 的一条 | `messages[].content` | `reasoning_effort` + `thinking.type=adaptive` |
| OpenAI Responses | `/responses` | **顶层** `instructions` | `input[].content[]` 的 `input_text` | `reasoning.effort` + `thinking.type=adaptive` |

★ **三条路径的注入语义必须一致**：授权声明都**拼进最后一条用户文本的末尾**。
Responses 很容易写成「另起一个 `input_text` block」——独立 block 的权重低于
同一条文本末尾，实测会造成软化漂移。

★ **注入必须幂等**：重试或同一 body 过两次时，内核与授权声明都**不得重复**。
每条路径注入前先查自己的标记串。

★ **system 缺失时要能自动创建**（客户端可能不带 system）。

## 三、代理必须满足的六条

1. **零依赖** —— 用 Python 标准库。别人 clone 下来 `python proxy.py` 就能跑。
2. **fail-soft** —— 注入抛异常时**放行原请求**，绝不把异常抛进请求路径。
   一个破甲代理把用户的 agent 搞挂，比不破甲更糟。
3. **key 透传** —— 默认透传客户端自己的 key，用户不必把 key 交给代理保管；
   可选 `--api-key-env` 指定兜底 key。
   ★ **header 名必须大小写不敏感地查找**（HTTP header 名本身大小写不敏感，
   不同客户端/库会写成 `X-Api-Key` / `x-api-key` / `Authorization`）。
   直接 `"x-api-key" in headers` 会漏判 ⇒ 误报 401。
   ★ 客户端只发其中一种时，**自动补齐另一种**（Anthropic 端点认 `x-api-key`，
   OpenAI 端点认 `Authorization: Bearer`），上游怎么挑都行。
4. **流式透传** —— SSE 要按 chunk 转发（chunked），不能缓冲成整体。
5. **可观测** —— 每条请求打一行摘要（协议 / status / kernel=Y/N / auth=Y/N /
   effort / 是否抬过输出上限）。代理的价值一半在于「能证明它在工作」。
6. **离线自测** —— `--self-test` 不发网络请求、不需要 key，
   断言「内核落地了 / 原内容还在 / 二次注入不重复 / 畸形输入不抛」。

## 四、★ 输出上限下限（客户端会设太低）

思考 token 与输出 token **共用** `max_tokens`。客户端若把上限设成 4096/8000，
模型思考花掉 7000 后正文被截断，上游报：

```
status=incomplete, reason=max_output_tokens
```

★ **这看起来像失败，其实内容写了一半**——标题往往已经写对了。
判据：正文空/半截 + `status=incomplete` ⇒ **不是拒答**，是上限不够。

⇒ 代理默认把输出上限抬到一个下限（`--min-output-tokens`，如 16000），
**并在日志里打出来**（`floor=16000`）——不能静默改用户的参数。
不想干预就设成 0。

★ 这条与「思考预算耗尽」是**两个不同的失败**：那个是模型思考量本身太大，
这个是客户端给的盒子太小。两者都要靠**加大上限**解决，都不是提示词问题。

## 五、base_url 的 `/v1` 陷阱

客户端对 base_url 要不要带 `/v1` **没有统一约定**，是代理类接入最高频的翻车点：

| 客户端类型 | base_url | 原因 |
|---|---|---|
| 客户端自己拼 `/chat/completions` | **带** `/v1` | 拼完就是 `/v1/chat/completions` |
| 客户端自己拼 `/v1/messages` | **不带** `/v1` | 它会自己加 |
| AI-SDK 系（拼 `/messages`） | **带** `/v1` | 拼完是 `/v1/messages` |

⇒ **代理按路径后缀识别，不要按 base_url 识别** ⇒ 两种写法都能吃。
⇒ 但**接入文档必须逐个 Agent 写清该填哪个**，不能只给一个通用示例。

★ **两类 client 只接受公网 HTTPS 端点**：它们的 BYOK 请求从**自己公司的服务器**
发出，不在你的机器上 ⇒ `127.0.0.1` 直连不通，必须上 tunnel。
⇒ 这条必须写进接入文档的显眼位置，否则用户照抄本地地址后只看到连接失败。

## 六、验收：必须有对照组

代理类交付的验收不能只看「经代理跑通了」，必须拿**同一用例集直连上游**做对照：

| 路径 | 拒答 | 免责 | 降级 |
|---|---|---|---|
| 直连上游（对照） | ?/N | ?/N | ?/N |
| 经代理 | ?/N | ?/N | ?/N |

★ 对照组是唯一的证据：**没有对照组，代理侧的好成绩说明不了任何事**。
★ 每条协议路径**分别**测（注入点不同，行为可能不同），并把各路径的已知弱点
**如实写进「已知限制」段**——不要挑好使的路径报，也不要藏弱点。

## 七、接入文档（`proxy/docs/AGENT-SETUP.md`）

逐个 Agent 写，**配置格式取自该 Agent 官方文档的真实示例**，不要自己编。
每个 Agent 至少给：base_url、api key 放哪、model id 字段叫什么。

★ **model id 要用正式上线的那个**，不是 preview。
★ 文档里还要有「四类典型翻车与对应修法」表（404/401/连不上/走了没破甲）。
★ 末尾加一句安全提醒：代理默认只听 `127.0.0.1`；若用 tunnel 暴露公网，
**务必加鉴权**，否则别人能用你的 key。

★ **别把这个文件也叫 `AGENTS.md`**：仓库根的 `AGENTS.md` 是**给 AI agent 读的执行
手册**（跨工具标准，多数 agent 原生读取），而这个是**逐个 client 的配置**——
同名含义相反，读者与 agent 都会混。

## 八、★ 让别的 AI 也能把它装起来

代理类交付的「可被采用性」不取决于代理多稳，而取决于**别人（或别人的 AI）
拿到仓库后能不能自己装上**。

⇒ **仓库根放 `AGENTS.md`**（Codex / Cursor / opencode / Claude Code / Aider /
Devin / Amp / Factory / Gemini CLI / Roo Code / Warp / Zed / goose 等原生读取），
内容是**给 agent 读的执行顺序**：clone → 离线自检 → 起代理 → 按客户端类型选
base_url → 两个高频坑 → key 透传规则 → **往返验证门槛**。
★ 里面要写明「**没做端到端验证不许宣布成功**」。

★ 再配一个一键脚本（`install.sh` / `install.ps1`）：定位解释器 → 离线自检 →
查端口 → 可选后台启动 → **打印要填的确切值**。

★ **干净 clone 端到端验证**才算数：全新 clone → 跑安装脚本 → 起代理 →
**同一 prompt 同时打「经代理」与「直连上游」**，并排列出拒答/字数/标题。

完整配方见技能 `open-source-release` 的 `references/ai-agent-onboarding.md`。

## 九、★ 代理是独立进程 ⇒ 必须做成开机自启

代理与框架原生插件的**持久性不同**：

| 载体 | 独立进程？ | 重启后 |
|---|---|---|
| 框架原生插件 / 中间件 | 否（宿主进程内） | **用户什么都不用做** |
| **本地代理** | **是** | **必须常驻** ⇒ 做成自启 |

⇒ 代理类交付要**自带自启脚本**（Windows 登录项 / systemd user unit / launchd），
并在接入文档与 `AGENTS.md` 的步骤里写明「装完就常驻」。

★ **自启脚本必须幂等**：先探 health 接口，已在跑就退出。
★ **验收自启的方式是打 health 接口 + 确认监听数为 1**，不是「脚本没报错」——
  静默失败时脚本退出码也是 0。
★ Windows 登录项有四个静默失败坑（写文件换行转换、登录项自己找本体、
  VBScript 嵌套引号数量、幂等缺失）——完整配方见技能 `open-source-release`
  的 `references/ai-agent-onboarding.md`。
