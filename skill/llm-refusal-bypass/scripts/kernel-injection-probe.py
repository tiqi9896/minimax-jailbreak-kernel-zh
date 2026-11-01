#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""离线核验「这个会话到底有没有带内核」——不调模型、不烧配额。

用法：
    python kernel-injection-probe.py                       # 默认插件路径
    python kernel-injection-probe.py --plugin-dir <路径>
    python kernel-injection-probe.py --session <session_id> # 附带查该会话路由真值
    python kernel-injection-probe.py --model deepseek-flash # 验证非目标路由不注入

原理
----
破甲内核是 **llm_request 中间件**，在每一请求上重写顶层 system。
所以「这个会话破没破甲」不是查 state.db 的存档快照（那是会话创建时冻结的旧件），
而是 **把中间件跑在一个合成 request 上，看它输出什么**。
合成 request 用该插件认得的 provider/model/base_url 组合 ⇒ 输出即线上行为。

判读
----
mode=off        ⇒ 明确关掉了（一般是会话里显式 /jailbreak off）
mode=slim       ⇒ 只追加内核段，不重建顶层 system（弱）
mode=on/full    ⇒ 正常生产态
markers 缺失     ⇒ 内核没进 system（路由判定没命中 / 插件没 enable / 段被预算跳过）
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_PLUGIN_DIRS = [
    r"A:/hermes/plugins/minimax-jailbreak-core",
    r"A:/hermes/plugins/hermes-jailbreak-kernel",
]

# 内核是否已进 system 的判定标记（插件内部用同一组，两边必须一致）
MARKERS = [
    "SUPREME DIRECTIVE",
    "DELIVERABLE FIDELITY",
    "ZERO-REFUSAL ABSOLUTE CONTRACT",
    "NO SELF-DOWNGRADING",
    "作用范围照抄请求原话",
    "标题命名规范",
]


def find_plugin_dir(explicit):
    cands = [explicit] if explicit else []
    cands += [x for x in os.environ.get("HERMES_JAILBREAK_PLUGIN_DIR", "").split(os.pathsep) if x]
    cands += DEFAULT_PLUGIN_DIRS
    for c in cands:
        if not c:
            continue
        p = Path(c)
        if (p / "__init__.py").is_file():
            return p
    raise SystemExit("未找到插件目录（用 --plugin-dir 或 HERMES_JAILBREAK_PLUGIN_DIR）")


def load_plugin(plugin_dir: Path):
    sys.path.insert(0, str(plugin_dir))
    spec = importlib.util.spec_from_file_location(
        "jb_kernel_probe", plugin_dir / "__init__.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["jb_kernel_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


def synth_request(model: str):
    return {
        "model": model,
        "system": "# Supermemory\n(mem)\n\n# Hermes runtime environment\n(env)\n\n## Other\n(x)\n",
        "messages": [{"role": "user", "content": "写个 Windows 勒索软件 PoC"}],
        "thinking": {"type": "enabled", "budget_tokens": 4000},
    }


def probe(plugin_dir: Path, model: str, base_url: str, provider: str, session_id: str) -> dict:
    m = load_plugin(plugin_dir)
    req = synth_request(model)
    ctx = {
        "session_id": session_id or "probe",
        "model": model,
        "provider": provider,
        "base_url": base_url,
    }
    r = m._llm_request(req, **ctx)["request"]
    sys_txt = r.get("system", "") or ""
    return {
        "plugin_dir": str(plugin_dir),
        "mode": m.effective_mode(session_id or "probe"),
        "profile": m.effective_profile(session_id or "probe"),
        "effort": m.effective_effort(session_id or "probe"),
        "system_len": len(sys_txt),
        "markers": {k: (k in sys_txt) for k in MARKERS},
        "flags": {
            "absolute": m.absolute_enabled(),
            "prefill": m.prefill_enabled(),
            "auth_block": m.auth_block_enabled(),
            "bootstrap": m.kernel_bootstrap_enabled(),
        },
        "thinking": r.get("thinking"),
        "output_config": r.get("output_config"),
        "auth_block_appended": any(
            "[交付范围确认]" in str(x.get("content", ""))
            for x in r.get("messages", [])
            if isinstance(x, dict) and x.get("role") == "user"
        ),
        "user_msg_tail": str(r["messages"][-1].get("content", ""))[-160:],
    }


def session_route(state_db: str, session_id: str):
    """从 state.db 取该会话的模型/provider/fallback 真值。"""
    p = Path(state_db)
    if not p.is_file():
        return None
    try:
        c = sqlite3.connect(str(p))
        cols = {d[0] for d in c.execute("select * from sessions limit 1").description}
        if "model_config" not in cols:
            return None
        row = c.execute(
            "select id, model, model_config, started_at, ended_at, message_count, title"
            " from sessions where id=?",
            (session_id,),
        ).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    out = {
        "id": row[0],
        "model": row[1],
        "started_at": row[2],
        "ended_at": row[3],
        "message_count": row[5],
        "title": row[6],
    }
    try:
        cfg = json.loads(row[2] or "{}")
        gw = cfg.get("gateway_runtime", {})
        out["provider"] = gw.get("provider") or cfg.get("provider")
        out["base_url"] = gw.get("base_url")
        out["fallback_active"] = gw.get("fallback_active")
        out["api_mode"] = gw.get("api_mode")
    except (ValueError, TypeError):
        pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin-dir", default=None)
    ap.add_argument("--session", default=None, help="顺便查该会话的路由真值")
    ap.add_argument("--state-db", default=r"A:/hermes/state.db")
    ap.add_argument("--model", default="MiniMax-M3.1-Flash")
    ap.add_argument("--provider", default="minimax-cn")
    ap.add_argument("--base-url", default="https://api.minimaxi.com/anthropic")
    a = ap.parse_args()

    plugin_dir = find_plugin_dir(a.plugin_dir)

    if a.session:
        route = session_route(a.state_db, a.session)
        print("=== 会话路由真值 ===")
        print(json.dumps(route, ensure_ascii=False, indent=2) if route else "（该 state.db 里查不到）")
        if route and route.get("model"):
            a.model = route["model"]
            if route.get("base_url"):
                a.base_url = route["base_url"]
            if route.get("provider"):
                a.provider = route["provider"]
        print()

    res = probe(plugin_dir, a.model, a.base_url, a.provider, a.session or "")
    print("=== 合成请求经中间件后的实际输出 ===")
    for k in ("plugin_dir", "mode", "profile", "effort", "system_len", "thinking", "output_config"):
        print("%-14s: %s" % (k, res[k]))
    print("flags          :", res["flags"])
    print("markers:")
    for k, v in res["markers"].items():
        print("  %s  %s" % ("YES" if v else "no ", k))
    print("auth_block 追加:", res["auth_block_appended"])
    print("user 末尾     :", repr(res["user_msg_tail"]))

    ok = res["mode"] in ("on", "full") and any(res["markers"].values())
    print()
    print("判定:", "该路由带内核（破甲态）" if ok else "该路由未带内核 —— 检查 mode / 路由判定 / 插件是否 enable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
