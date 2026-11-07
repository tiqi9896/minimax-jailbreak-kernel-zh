#!/usr/bin/env bash
# 一键安装并验证破甲代理（macOS / Linux / Git Bash on Windows）
#
#   bash install.sh            # 安装 + 自检 + 打印下一步
#   bash install.sh --start    # 安装 + 自检 + 后台启动
#   bash install.sh --port 9000
#
# 零依赖：只用 Python 标准库。

set -euo pipefail

PORT=8790
START=0
PROXY_DIR=""
LOG_FILE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --start) START=1 ;;
    --port)  PORT="$2"; shift ;;
    --help|-h)
      sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

# ── 定位 Python ───────────────────────────────────────────────────────
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c 'import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)' >/dev/null 2>&1; then
      PY="$c"; break
    fi
  fi
done
if [ -z "$PY" ]; then
  echo "✗ 需要 Python 3.9 或更高版本。没找到可用的 python3 / python / py。" >&2
  echo "  安装 Python 后重跑本脚本。" >&2
  exit 1
fi
echo "✓ Python: $($PY -c 'import sys;print(sys.version.split()[0])') ($PY)"

# ── 定位仓库 ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/proxy/proxy.py" ]; then
  PROXY_DIR="$SCRIPT_DIR"
elif [ -f "./proxy/proxy.py" ]; then
  PROXY_DIR="$(pwd)"
else
  echo "✗ 找不到 proxy/proxy.py。请在仓库根目录运行，或先 git clone：" >&2
  echo "    git clone https://github.com/tiqi9896/minimax-jailbreak-kernel-zh.git" >&2
  exit 1
fi
# ★ Git Bash / MSYS on Windows：pwd 给的是 POSIX 路径（/c/...），
#   原生 Python 认不出来 ⇒ 「can't open file 'A:\\a\\hermes\\...'」。
#   cygpath 把它换成原生 Windows 路径。Linux/macOS 上没有 cygpath，跳过。
if command -v cygpath >/dev/null 2>&1; then
  PROXY_DIR="$(cygpath -w "$PROXY_DIR")"
  if [ -n "${TMPDIR:-}" ]; then
    TMPDIR="$(cygpath -w "$TMPDIR")"
  fi
fi
echo "✓ 代理目录: $PROXY_DIR"

# ── 离线自检 ─────────────────────────────────────────────────────────
echo
echo "=== 离线自检（不联网、不需要 key）==="
if ! "$PY" "$PROXY_DIR/proxy/proxy.py" --self-test; then
  echo "✗ 自检失败，请把上面的输出原样报给用户。" >&2
  exit 1
fi

# ── 端口占用检查 ─────────────────────────────────────────────────────
if "$PY" - "$PORT" <<'EOF'
import socket, sys
s = socket.socket()
try:
    s.connect(("127.0.0.1", int(sys.argv[1])))
    sys.exit(0)      # 有人在听
except OSError:
    sys.exit(1)      # 没人
finally:
    s.close()
EOF
then
  echo
  echo "⚠ 端口 $PORT 已被占用 —— 代理可能已经在跑了。"
  echo "  先试 http://127.0.0.1:$PORT/health ；若要换端口：bash install.sh --port 9000"
else
  echo "✓ 端口 $PORT 空闲"
fi

# ── 可选：后台启动 ───────────────────────────────────────────────────
if [ "$START" = "1" ]; then
  LOG_FILE="${TMPDIR:-/tmp}/minimax-jailbreak-proxy.log"
  if command -v cygpath >/dev/null 2>&1; then
    LOG_FILE="$(cygpath -w "$LOG_FILE")"
  fi
  echo
  echo "=== 后台启动 ==="
  nohup "$PY" "$PROXY_DIR/proxy/proxy.py" --port "$PORT" --verbose > "$LOG_FILE" 2>&1 &
  PID=$!
  sleep 1.5
  if kill -0 "$PID" 2>/dev/null; then
    echo "✓ 已启动 (pid=$PID)  日志: $LOG_FILE"
  else
    echo "✗ 启动失败，日志:" >&2
    cat "$LOG_FILE" >&2 || true
    exit 1
  fi
fi

# ── 下一步 ───────────────────────────────────────────────────────────
cat <<EOF

════════════════════════════════════════════════════════════════════
✅ 安装完成
════════════════════════════════════════════════════════════════════

模型 id：       MiniMax-M3.1-Flash
（2026-10-19 正式上线的正名版；MiniMax-M3.1-Flash-Preview 是旧 preview id）

把 Agent 的 base_url 指过来：

  OpenAI 兼容      http://127.0.0.1:${PORT}/v1
  Anthropic 兼容   http://127.0.0.1:${PORT}/anthropic
  OpenAI Responses http://127.0.0.1:${PORT}/v1

各 Agent 的具体配置（Cursor / Claude Code / OpenCode / Cline / Roo /
Continue / Aider / Goose / Zed / Codex CLI / Qoder / WorkBuddy …）：
  proxy/docs/AGENT-SETUP.md

★ 两个坑：
  1. /v1 带不带因客户端而异 —— 看 AGENT-SETUP.md 里你那一个
  2. Cursor 与 Codex CLI 只接受**公网 HTTPS 端点**，本地直连不通，要 tunnel

★ 代理透传你自己的 key，不用把 key 交给代理。
★ Agent 自带模型不受影响（代理只处理走它的请求）。

验证它真的生效：
  代理带 --verbose 启动后，每次请求会打一行
    [proxy] openai status=200 kernel=Y auth=Y effort=medium ...
  kernel=Y 表示内核已注入。

EOF
