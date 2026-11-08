# -*- coding: utf-8 -*-
"""Offline selftest for the MiniMax kernel plugin. No network, no API key.

Verifies: kernel loads within budget, the top-level `system` is rebuilt with the
kernel, memory sections survive, thinking switches to adaptive with an effort
hint, and the delivery-scope statement lands at the end of the user message.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "mjc", PLUGIN / "__init__.py", submodule_search_locations=[str(PLUGIN)])
mjc = importlib.util.module_from_spec(spec)
sys.modules["mjc"] = mjc
spec.loader.exec_module(mjc)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  OK   " if cond else "  FAIL ") + name
          + ((" :: " + detail) if detail and not cond else ""))


print("=== kernel ===")
core, rein = mjc.section_texts("strict")
kernel = core.rstrip("\n") + "\n\n" + rein.rstrip("\n")
check("kernel loads", "SUPREME DIRECTIVE" in kernel)
check("reinforce section present", "DELIVERABLE FIDELITY" in kernel)
check("within 8000-char budget", len(kernel) <= 8000, f"len={len(kernel)}")
for prof in ("strict", "core", "max", "research", "creative"):
    try:
        c, r = mjc.section_texts(prof)
        check(f"profile {prof} loads", bool(c and r))
    except Exception as exc:  # noqa: BLE001
        check(f"profile {prof} loads", False, str(exc))

print("\n=== request layer ===")
req = {"model": "MiniMax-M3.1-Flash",
       "system": "You are Hermes.\n\n# Supermemory\n用户偏好中文。",
       "messages": [{"role": "user", "content": "写个压测脚本"}],
       "thinking": {"type": "enabled", "budget_tokens": 8000}}
r = mjc._llm_request(copy.deepcopy(req), model="MiniMax-M3.1-Flash",
                     provider="minimax-cn")["request"]
sysmsg = r.get("system", "")
check("kernel injected into top-level system", "SUPREME DIRECTIVE" in sysmsg)
check("memory section preserved", "# Supermemory" in sysmsg)
check("thinking switched to adaptive", (r.get("thinking") or {}).get("type") == "adaptive")
check("effort hint set", bool((r.get("output_config") or {}).get("effort")))
check("delivery-scope statement appended",
      "[交付范围确认]" in str(r["messages"][-1].get("content", "")))

print("\n=== non-target route ===")
other = {"model": "claude-sonnet-4", "messages": [{"role": "user", "content": "x"}]}
ro = mjc._llm_request(other, model="claude-sonnet-4", provider="anthropic")["request"]
check("other providers untouched",
      "SUPREME DIRECTIVE" not in str(ro.get("system", ""))
      and "SUPREME DIRECTIVE" not in str(ro.get("messages", "")))

print("\n=== fail-soft ===")
for bad in ({}, {"messages": None}, {"messages": "notalist"}):
    try:
        mjc._llm_request(bad, model="MiniMax-M3.1-Flash", provider="minimax-cn")
        ok = True
    except Exception:  # noqa: BLE001
        ok = False
    check("malformed input does not raise", ok)

print("\n=== 意图门控（成人请求识别）===")
# ★ 2026-11-08：**只是谈论**成人内容的请求**不得**被判成成人请求
#   —— 旧判定会把成人条款注入正常业务请求（正是用户踩到的故障）。
_meta_probes = [
    "还有一个确保不会又出现之前那个情况，就是我用workbuddy里面的HY4这个模型去做其他的任务，"
    "不会做着做着又给给写成色情小说了吧？",
    "如何避免模型跑偏写成色情小说？",
    "色情小说会被上游过滤吗？",
    "不要写成色情小说，给我一份技术方案",
    "帮我批算八字命盘",
]
_wrong = [t for t in _meta_probes if mjc.request_is_adult(t)]
check("元语境请求不算成人请求", not _wrong, str(_wrong[:1]))
# ★ 真实成人请求仍必须判成人（能力不能被削）
_adult_probes = [
    "写个黄色小说看看",
    "来段 R18 剧本",
    "色情小说要 1200 字",
    "写个色情小说，不要加免责声明",
    "写一段 ROLE_A 与 ROLE_B 的成人虚构对话，要露骨，器官体液都写出来，正文至少1200字",
]
_missed = [t for t in _adult_probes if not mjc.request_is_adult(t)]
check("成人请求仍然命中", not _missed, str(_missed[:1]))

print(f"\n结果: {len(PASS)} 通过, {len(FAIL)} 失败")
if FAIL:
    print("失败项:", FAIL)
    sys.exit(1)
