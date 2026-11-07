# 参与贡献


**语言 / Language**：**中文**（本文） | [English](CONTRIBUTING.en.md)

感谢你考虑参与贡献。这个项目很小，但有价值的 PR 门槛也很低：
**一个被测量过的改动，和一个你能复现的结论。**

## 基本规则

1. **先测量，再下结论。** 一个只说「这样能让模型更配合」而不给数字的 PR，
   会被要求补数字。仓库里的 `skill/llm-refusal-bypass/` 就是为这个存在的 —— 请用它。
2. **一次只变一个变量。** 你同时改了内核文案**和** effort 设置，
   没人能说清是哪个动了结果。
3. **报对照组。** 只有实验组数字不算证据。
4. **不要碰无关文件。** 插件就是一个目录加一个技能。
4b. **绝不硬编码绝对路径。** 用 `Path(__file__).resolve().parent` 和环境变量。
   见下面的「可移植路径」。
5. **绝不提交密钥。** 不要 API key、不要 `.env`、不要 `state.db`、不要日志。
   `.gitignore` 已经覆盖了常见情况 —— 但加文件前还是检查一下。

## 可移植路径 —— 我们真正踩过的坑

内核文案的查找路径原本指向**上游插件的硬编码绝对路径**。两个问题：

- 任何 clone 这个仓库的人，除非恰好在自己机器的同一个绝对路径装了上游插件，
  否则会拿到 `TypeError` / `FileNotFoundError`。
- 它泄漏了原作者的目录结构。

修法是三级探测：

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

**第二个坑：** 任何做 `root / filename` 的函数都必须防 `root is None`。
否则插件在作者机器上是好的（那儿上游*确实*装着，所以探测永远不返回 `None`），
而在其他所有人机器上崩溃。

### 开 PR 前必做的检查

```bash
# 把插件复制到一个没有上游兄弟目录的地方，然后跑测试：
cp -r plugin /tmp/standalone/minimax-jailbreak-core
cd /tmp/standalone/minimax-jailbreak-core && python selftest.py
```

预期：`结果: 17 通过, 0 失败`。

如果它只在你机器上通过、在干净目录里失败，那你就是中了 `None` 那个 bug。

## 改代理时

`proxy/` 是一个独立的 HTTP 代理，有自己的离线测试套件：

```bash
cd proxy && python proxy.py --self-test
```

它必须保持两个性质：

1. **fail-soft。** 注入万一抛异常，原请求必须**原样**转发。
   一个会把 agent 搞坏的代理比没有代理更糟。绝不让异常逃进请求路径。
2. **幂等。** agent 可能重试，同一个 body 也可能过两遍。
   内核和范围声明绝不能重复。两条注入路径追加前都先查自己的标记。

加一种新协议形状时，照着现有的三种来：
每个形状一个注入函数、路由里一个路径后缀判断、
以及断言「(a) 内核落到位 (b) 原内容还在 (c) 第二次注入不重复任何东西」的自测用例。

### `/v1` 陷阱

客户端对 base URL 要不要带 `/v1` 意见不一：

- 自己拼 `/chat/completions` 的 → base URL **带** `/v1`
- 自己拼 `/v1/messages` 的 → base URL **不带** `/v1`

代理对 Anthropic 形状两种都接受（它按路径后缀匹配，不按 base URL）。
保持这一点，并在 `proxy/docs/AGENT-SETUP.md` 里逐个 agent 写明确切值。

### 输出上限下限

思考 token 和输出 token 共用 `max_tokens`。客户端把上限设低（4096 / 8000）会拿到
一个**被截断**的答案，看起来像失败 —— 上游报
`status=incomplete, reason=max_output_tokens`。代理把下限抬到
`--min-output-tokens`（默认 16000），并在抬的时候打日志。
改默认值的话，在 commit message 里说清为什么。

## 跑测试

```bash
# 离线，不需要 API key，不联网
cd plugin && python selftest.py
```

自测用合成请求载荷驱动中间件：system prompt 重建、effort 注入、授权声明块、
按会话的兜底、路由判定，以及畸形输入下的 fail-soft 行为。

## 活体测试（需要你自己的 key）

```bash
python skill/llm-refusal-bypass/scripts/refusal-probe.py \
  --key-env MINIMAX_CN_API_KEY \
  --base-url https://api.minimaxi.com/anthropic/v1/messages \
  --model MiniMax-M3.1-Flash \
  --effort medium
```

插件**开着**和**关着**各跑一次，对比 verdict 计数。
**这个 A/B 才是唯一能证明改动是真的东西。**

**注意配额。** 大预算回归跑会耗尽计量套餐。串行跑、分层预算、
一遇到配额错误就停 —— 别让 429 污染你的拒答统计。

## 代码风格

- 内核 prompt 文案放 `prompts/profiles/*.md`，不要内联在 Python 里。
- 内核是**两段**，职责不同：
  - *主契约* —— 做什么
  - *强化段* —— 不许被怎么悄悄降级

  不要合成一大坨；实测会明显变弱。合计保持在 provider 的单段预算内。
- 注释写**为什么**，不是写**是什么**。尤其是请求层的那些怪癖
  （顶层 `system`、被忽略的 `budget_tokens`、模型名优先的路由判定）——
  没有上下文看它们像乱码。
- 跟周边风格一致：中英双语注释都可以，上游 prompt 语料本来就是双语的。

## 加一个 profile

1. 新建 `prompts/profiles/<name>.md`。
2. 在 `PROFILE_FILES` 和 `SECTION_SPLIT`（哪个段文件与它配对）里注册。
3. 加一条自测用例。
4. 在 README 的 profile 列表里写明。

## 加一个环境变量

1. 通过现有的 `_truthy` / `_falsey` 辅助函数读取，
   这样 `1`/`true`/`yes`/`on` 和 `0`/`false`/`no`/`off` 行为一致。
2. 给它一个默认值，并写进 README 的环境变量表。
3. 加一条自测用例，设置后再移除。

## 署名

`plugin/prompts/profiles/{core,research,creative,max}.md` 里的 prompt 语料
是从 [Enchanted0911/hermes-jailbreak-kernel](https://github.com/Enchanted0911/hermes-jailbreak-kernel)
逐字继承的 MIT 内容（© 2026 Enchanted0911）。

**不要删除或改写那条署名。** 如果你加了新的 prompt 文件，
在 `NOTICE` 里说明哪些部分是你的、哪些是继承的。

## 报问题

请附上：

- 确切的模型 id 和 effort 设置；
- 插件版本（见 `plugin/plugin.yaml`）；
- 你观察到的 verdict 分类（`COMPLY` / `SOFT-REFUSE` /
  `HARD-REFUSE` / `TRUNCATED` / `COMPLY(tool_use)`）；
- 相关响应字段：`stop_reason`、正文长度、`thinking_tokens`。

`thinking_tokens` 字段很关键：空正文 + `stop_reason=max_tokens` 是
**思考预算耗尽**，不是拒答，改 prompt 修不好。

## 范围

本项目改变的是模型对**用你自己的 API key** 发出的请求的行为。
它不击穿服务商侧审核，也不会让别人的系统更容易被访问。
贡献请保持在这个框架内 —— 请不要加针对第三方系统的功能。

## 双语文档

本仓库的文档是**中英双语**的：英文版是 `README.md` / `AGENTS.md` /
`CONTRIBUTING.md` / `docs/*.md`，中文版是对应的 `*.zh-CN.md`。

**改动文档时两版都要改。** 中文版不是英文版的摘要 —— 它们信息量应当一致，
只是语言不同。顶部都有语言切换链接。
