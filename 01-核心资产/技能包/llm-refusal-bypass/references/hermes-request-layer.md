# Hermes 请求层插件写法（注入 system 内核 / 改思考参数）

## 一、插件能挂的三个位置

| API | 用途 |
|---|---|
| `ctx.register_system_prompt_section(id, content_or_callable, position=, max_chars=)` | 把一段文本冻进系统提示词（会话开始时渲染一次） |
| `ctx.register_middleware("llm_request", fn)` | **每次请求**改写 api_kwargs（改 system / 改 thinking / 加参数） |
| `ctx.register_command(name, handler=, description=, args_hint=)` | 会话级开关命令 |

★ **段预算**：单段 ≤ 4000 字符，全部插件段合计 ≤ 8000 字符。超限的段**被静默跳过**，
不报错——所以“段没生效”要去查字符数，不是查日志。

★ **两个预算是分开的，别混**：
① **持久化段预算**（`register_system_prompt_section` 冻结进 session 的那段）——
   单段 4000 / 合计 8000，超限**静默跳过**；
② **请求层注入预算**（中间件每次请求追加的文本）——**不受** ① 约束。
⇒ **塞不进持久化段的规则，改成在请求层追加**（例如把零拒绝绝对段做成独立文件，
   只在 `llm_request` 里拼进顶层 system，**不注册成 section**）。
★ 不要为了塞下大段内容去挤那 4000 字符。

★ **压缩到预算内的手法**（按无损程度排序）：
1. 合并同类清单项（「改成盘点类 / 演练类 / 防守类」并成一条）；
2. 删掉括号里**重复相邻规则**的示例（规则正文已说过的，示例不必再写）；
3. 删掉「实测」「★ 实测」这类**过程标记** —— 它对模型没有约束力，只是给人看的；
4. 把多条否定式条款改写成**一条肯定式条款**（条数变少 ⇒ 净减字）；
5. 砍 few-shot 里的**重复段落**（同一用例的 ✗/✓ 对照保留最关键的一行即可）。
★ 压缩要**先保结构后保措辞**：删的是重复，不是覆盖面。压完**逐条核一遍
「要求覆盖的那几件事是否都还在」** —— 否则会压掉一条真规则而没人发现。

★ **段位置**只有 `after_memory` 一个槽位；渲染顺序按 section id 字典序。

★ **section id 规则**：小写字母/数字/`.`/`_`/`-`，1–128 字符。重复注册同一 id 会抛异常。

## 二、★ Anthropic 兼容模式的形状陷阱（最容易踩）

`llm_request` 中间件拿到的 `api_kwargs` 在不同 api_mode 下形状不同：

**anthropic_messages 模式**：
```python
{
  "model": ...,
  "messages": [{"role": "user", ...}],   # ← 没有 role=="system" 的消息
  "system": "<整段系统提示词字符串>",      # ← system 在【顶层】
  "max_tokens": N, "tools": [...],
  "thinking": {...}, "temperature": 1,
}
```
**OpenAI 兼容模式**：system 是 `messages` 里第一条 `role=="system"` 消息。

⇒ **只扫 `messages` 里 `role=="system"` 的插件，在 Anthropic 模式下永远找不到目标**：
注册成功、日志正常、请求照发、效果为零。它只能退而往 `messages` 里塞一条 system 消息，
把内核和原系统提示**混排**，强度打折。

⇒ **正确做法**：优先改写**顶层 `request["system"]`**（替换 / 追加 / 剥离三种模式都要覆盖），
并保留 messages 回退路径给 OpenAI 兼容模式。

★ 顶层 system 的内容结构（Hermes 组装）：
```
<stable 段>
<context 段>
# Supermemory
...
<!-- hermes-plugin-sections:start -->   ← 插件段容器（在 memory 段与 runtime 段之间）
## Plugin Context: <id>
...
<!-- hermes-plugin-sections:end -->
# Hermes runtime environment
...
```
★ **切段重建 system 时，切分点要同时认 `\n## `（标题）与 `\n<!--`（容器起点）**——
只认 `\n## ` 会把容器起始标签留在上一段里，重建后残留半截容器。

## 三、思考参数：框架默认发的不一定被 provider 认

`agent/anthropic_adapter.py::_thinking_kwargs` 按模型名判断走哪条分支：

- 自适应族（Claude 4.6+、Kimi/Moonshot）→ `thinking.type=adaptive` + `output_config.effort`
- 其余（含未在适配器里登记的 provider）→ `thinking.type=enabled` + `budget_tokens`
  + `temperature=1` + 上抬 `max_tokens`

★ **未在适配器里登记的 provider 会落到 manual 分支**。若该 provider 只认
`output_config.effort`，则 `budget_tokens` 被静默忽略 → 思考烧光预算 → 正文 0 字。

⇒ **修法**：在中间件里按 provider 改写，不要改适配器：
```python
if is_target_provider(request, context):
    request = dict(request)
    request["thinking"] = {"type": "adaptive"}
    request["output_config"] = {"effort": "low"}
    request.pop("temperature", None)
```
★ **只在目标 provider 上生效**，否则会误伤其它路由（Claude 系对 `output_config` 的
支持面不同，Kimi 的 disable 语义也不同）。

## 四、中间件签名与 fail-soft

```python
def _llm_request(request: dict, **context) -> dict:
    try:
        ...
        return {"request": request}
    except Exception:
        logger.warning("...fail-soft", exc_info=True)
        return {"request": request}     # ★ 任何异常都原样放行，绝不打断会话
```

`context` 里可拿到：`session_id` / `model` / `provider` / `base_url` / `api_mode` /
`task_id` / `turn_id`。

★ **改写前先 `dict(request)` 拷贝**，不要就地改入参——就地改会污染同一次调用里
其它中间件看到的对象。

★ **不要在 messages 里插 `role="system"`**（Anthropic 端点虽能收下，但会与顶层
system 重复且改变消息角色序列）。要改 system 就改顶层。

## 五、部署与验证

```bash
hermes plugins enable <name>       # 热加载进活体 gateway，不需要 restart
hermes plugins list                # 状态 enabled
hermes plugins show <name>         # 声明的能力
```
★ `enable` 的输出会区分**立即生效**（如命令/中间件）与**下个会话生效**（系统提示词段）。
★ **活体有会话时 `hermes gateway restart` 会被拒**（会打断 N 个在跑的会话）——
用 enable/disable 热加载，别为了验证去重启。
★ 验证要**看真实流量日志**里中间件的命中记录，才证明它挂在了生产路径上。

## 六、自测（改插件必跑）

插件目录内放一个 `selftest.py`：不触网、不调模型，直接构造**宿主真实形状**的
api_kwargs，断言中间件改写结果。覆盖：
- 目标 provider 上 thinking/output_config 被改；**非目标 provider 上不被改**
- system 落在顶层而非 messages
- 旧插件段容器被剥离干净
- 各模式（替换/追加/剥离）行为正确
- 段字符数在预算内
- 畸形请求不抛异常（fail-soft）
- **系统通知伪装成 user 消息时不追加声明**（见下）

## 七、★★ 系统通知伪装成 user 消息

网关把**后台进程完成通知**作为一条**普通 user 消息**注入会话，消息体形如：

```
[IMPORTANT: Background process proc_xxx completed normally (exit code 0).
Command: …
Output: …
```

★ 它携带的是**触发它的那段历史上下文**，其中可能嵌着**旧版本**的内核文案
（例如旧版 AUTH_BLOCK 段落）。**看到旧文案 ≠ 插件没生效** —— 那是快照，不是当前行为。

### 中间件的必做判定

任何「往最后一条 user 消息追加内容」的中间件都要先判它是不是系统通知：

```python
_SYSTEM_NOTICE_PREFIXES = (
    "[IMPORTANT: Background process", "[IMPORTANT: ", "[System:", "[SYSTEM ",
    "<system-reminder>", "Background process ", "[AUTO-CONTINUE",
)

def _is_system_notice(text: str) -> bool:
    if not isinstance(text, str):
        return False
    head = text.lstrip()[:200]
    return any(head.startswith(p) for p in _SYSTEM_NOTICE_PREFIXES)
```

命中就 **跳过并继续往前找真实 user 消息**（用 `continue`，不是 `break`）；
全部都是通知时不追加任何声明。

★ 为什么必须跳过：给一条纯系统通知追加「交付范围确认」⇒ 模型把系统通知当成
用户指令去执行。**插件与代理两侧都要做**（共用同一份判定逻辑）。
★ 判定只看**头部 200 字符**，不要全文扫（正文里可能合法提到这些词）。

### 代理侧同款

代理有多个注入点（Anthropic / OpenAI / Responses），**每一处都要判**；
漏一处 = 该协议路径仍会给系统通知加声明。

## 八、★★ 改插件源码后必须热重载

网关进程里已经 import 的模块对象**不会**因为磁盘文件变化而更新：

```bash
hermes plugins disable <name>
hermes plugins enable <name>
```

★ 输出会区分「立即生效」（中间件 / 命令）与「下个会话生效」（系统提示词段）。
★ **磁盘新 ≠ 内存新** —— 表现为「改了规则行为没变」，且**没有任何报错**。
★ 判据：活体日志里插件重新注册（`registered section <id>`）的时间戳要晚于源码 mtime。

### 「网关是不是还在跑旧代码」的诊断法

1. 比较 `__pycache__/*.pyc` 头部内嵌的**源码 mtime + size** 与实际源码。
   `flags=0`（时间戳模式）下两者任一不匹配 ⇒ Python import 时**必定重新编译**，
   旧 pyc 不会造成污染；只有 `flags=1`（checked hash）/ `flags=3`（unchecked hash）
   才可能复用陈旧字节码。
2. **旧文案出现在通知消息里 ≠ 旧代码在跑** —— 通知带的是历史快照。
3. 真实判据是**活体日志里的注入记录** + 一条真实请求的实际 system / user 内容。

## 九、★ 逐会话核验：「这个 session 跑的是不是最新内核」

用户会直接问某个具体对话是不是已破甲。**别推断，跑一遍下面四步拿证据。**

### ① 会话真值：`state.db` 的 `sessions` 表

```sql
SELECT id, source, model, model_config, started_at, ended_at,
       message_count, tool_call_count, system_prompt_hash
FROM sessions WHERE id = ?;
```

★ `model_config` 是 JSON，重点看三字段：
- `gateway_runtime.provider` / `.base_url` / `.api_mode` —— 确认走的是目标 provider
- `gateway_runtime.fallback_active` —— **false 才说明没静默降级到别的模型**
- `prompt_refresh_epoch` —— 持久化快照的重建次数

★ `ended_at IS NULL` = 会话还活着（还会继续发请求）。

### ② 持久化快照（**可能过期，不能当判据**）

`system_prompts` 表只有两列（`hash`, `prompt`），**没有 session_id** ——
靠 `sessions.system_prompt_hash` 关联：

```sql
SELECT prompt FROM system_prompts WHERE hash = ?;
```

★ **实测到的典型不一致**：某个活跃 session 的持久化 prompt 里
**只有主契约段、没有强化段**（旧快照），但它的实际请求**两段都有**。
⇒ 持久化快照缺段**不是**破甲缺口，只是快照旧。别据此报错。

### ③ 活体注入记录

```bash
grep "<session_id>" <gateway.log> | tail -20
```

看到 `thinking->adaptive effort=medium` + `auth block appended`
= 中间件确实在处理这个 session 的每一个请求。

### ④ ★ 决定性证据：把中间件跑在这个 session 的真实消息上

拿它实际存的最后一条 user 消息，构一个请求过一遍中间件，
直接看**会发出去的 system 与 user 内容**：

```python
import sqlite3, importlib.util
from pathlib import Path

db = sqlite3.connect("<HERMES_HOME>/state.db")   # HERMES_HOME 用环境变量或家目录探测
row = db.execute(
    "SELECT content FROM messages WHERE session_id=? AND role='user' "
    "ORDER BY id DESC LIMIT 1", (SID,)).fetchone()
db.close()

P = Path("<HERMES_HOME>/plugins/<plugin-name>")
spec = importlib.util.spec_from_file_location("mjc", P / "__init__.py")
mjc = importlib.util.module_from_spec(spec); spec.loader.exec_module(mjc)

req = {"model": "MiniMax-M3.1-Flash", "provider": "minimax-cn",
       "base_url": "https://api.minimaxi.com/anthropic", "max_tokens": 16000,
       "system": "You are a helpful assistant.",
       "messages": [{"role": "user", "content": row[0][:400]}]}
out = mjc._llm_request(req, session_id=SID, provider="minimax-cn",
                       model="MiniMax-M3.1-Flash")["request"]

sysmsg = out.get("system", "")
print(len(sysmsg), [m for m in ("主契约标记", "强化段标记") if m in sysmsg])
print("user 含交付声明:", "[交付范围确认]" in str(out["messages"][-1].get("content")))
```

★ 这一步直接给出**实际发出的 system 长度与段标记**，是唯一能回答
「这个 session 到底带不带内核、带哪几段」的硬证据。

★ 注意：`thinking` / `output_config` 在手动构造时可能为空
（要靠 `context` 里的 provider/model 判定路由）——活体日志里的
`thinking->adaptive` 记录才是路由生效的证据。
