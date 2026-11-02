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

print(f"\n结果: {len(PASS)} 通过, {len(FAIL)} 失败")
if FAIL:
    print("失败项:", FAIL)
    sys.exit(1)
