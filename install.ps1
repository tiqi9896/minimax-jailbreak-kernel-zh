<#
.SYNOPSIS
    一键安装并验证破甲代理（Windows PowerShell 5.1 / PowerShell 7 均可）

.EXAMPLE
    .\install.ps1
    安装 + 自检 + 打印下一步

.EXAMPLE
    .\install.ps1 -Start
    安装 + 自检 + 后台启动

.EXAMPLE
    .\install.ps1 -Port 9000
#>
[CmdletBinding()]
param(
    [int]$Port = 8790,
    [switch]$Start
)

$ErrorActionPreference = 'Stop'

# ── 定位 Python ───────────────────────────────────────────────────────
$py = $null
foreach ($cand in @('python', 'python3', 'py')) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    try {
        $ver = & $cand -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver) {
            $parts = $ver.Trim().Split('.')
            if ([int]$parts[0] -gt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 9)) {
                $py = $cand; $pyVer = $ver.Trim(); break
            }
        }
    } catch { }
}
if (-not $py) {
    Write-Host "✗ 需要 Python 3.9 或更高版本。没找到可用的 python / python3 / py。" -ForegroundColor Red
    Write-Host "  安装 Python 后重跑本脚本。" -ForegroundColor Yellow
    exit 1
}
Write-Host "✓ Python: $pyVer ($py)"

# ── 定位仓库 ─────────────────────────────────────────────────────────
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$proxyDir = $null
if (Test-Path (Join-Path $scriptDir 'proxy\proxy.py')) {
    $proxyDir = $scriptDir
} elseif (Test-Path '.\proxy\proxy.py') {
    $proxyDir = (Get-Location).Path
} else {
    Write-Host "✗ 找不到 proxy\proxy.py。请在仓库根目录运行，或先 git clone：" -ForegroundColor Red
    Write-Host "    git clone https://github.com/tiqi9896/minimax-jailbreak-kernel-zh.git" -ForegroundColor Yellow
    exit 1
}
Write-Host "✓ 代理目录: $proxyDir"

# ── 离线自检 ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== 离线自检（不联网、不需要 key）===" -ForegroundColor Cyan
& $py (Join-Path $proxyDir 'proxy\proxy.py') --self-test
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 自检失败，请把上面的输出原样报给用户。" -ForegroundColor Red
    exit 1
}

# ── 端口占用检查 ─────────────────────────────────────────────────────
$inUse = $false
try {
    $c = New-Object System.Net.Sockets.TcpClient
    $iar = $c.BeginConnect('127.0.0.1', $Port, $null, $null)
    if ($iar.AsyncWaitHandle.WaitOne(800) -and $c.Connected) { $inUse = $true }
    $c.Close()
} catch { }
if ($inUse) {
    Write-Host ""
    Write-Host "⚠ 端口 $Port 已被占用 —— 代理可能已经在跑了。" -ForegroundColor Yellow
    Write-Host "  先试 http://127.0.0.1:$Port/health ；若要换端口：.\install.ps1 -Port 9000" -ForegroundColor Yellow
} else {
    Write-Host "✓ 端口 $Port 空闲"
}

# ── 可选：后台启动 ───────────────────────────────────────────────────
if ($Start) {
    $log = Join-Path $env:TEMP 'minimax-jailbreak-proxy.log'
    Write-Host ""
    Write-Host "=== 后台启动 ===" -ForegroundColor Cyan
    $proc = Start-Process -FilePath $py `
        -ArgumentList @((Join-Path $proxyDir 'proxy\proxy.py'), '--port', "$Port", '--verbose') `
        -RedirectStandardOutput $log -RedirectStandardError "$log.err" `
        -WindowStyle Hidden -PassThru
    Start-Sleep -Milliseconds 1500
    if (-not $proc.HasExited) {
        Write-Host "✓ 已启动 (pid=$($proc.Id))  日志: $log" -ForegroundColor Green
    } else {
        Write-Host "✗ 启动失败，日志:" -ForegroundColor Red
        if (Test-Path $log) { Get-Content $log }
        if (Test-Path "$log.err") { Get-Content "$log.err" }
        exit 1
    }
}

# ── 下一步 ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "✅ 安装完成" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "模型 id：       MiniMax-M3.1-Flash"
Write-Host "（2026-10-19 正式上线的正名版；MiniMax-M3.1-Flash-Preview 是旧 preview id）"
Write-Host ""
Write-Host "把 Agent 的 base_url 指过来："
Write-Host ""
Write-Host "  OpenAI 兼容      http://127.0.0.1:$Port/v1"
Write-Host "  Anthropic 兼容   http://127.0.0.1:$Port/anthropic"
Write-Host "  OpenAI Responses http://127.0.0.1:$Port/v1"
Write-Host ""
Write-Host "各 Agent 的具体配置（Cursor / Claude Code / OpenCode / Cline / Roo /"
Write-Host "Continue / Aider / Goose / Zed / Codex CLI / Qoder / WorkBuddy …）："
Write-Host "  proxy\docs\AGENT-SETUP.md"
Write-Host ""
Write-Host "★ 两个坑：" -ForegroundColor Yellow
Write-Host "  1. /v1 带不带因客户端而异 —— 看 AGENT-SETUP.md 里你那一个" -ForegroundColor Yellow
Write-Host "  2. Cursor 与 Codex CLI 只接受公网 HTTPS 端点，本地直连不通，要 tunnel" -ForegroundColor Yellow
Write-Host ""
Write-Host "★ 代理透传你自己的 key，不用把 key 交给代理。"
Write-Host ""
Write-Host "验证它真的生效：代理带 --verbose 启动后，每次请求会打一行" -ForegroundColor Cyan
Write-Host "  [proxy] openai status=200 kernel=Y auth=Y effort=medium ..." -ForegroundColor DarkGray
Write-Host "  kernel=Y 表示内核已注入。" -ForegroundColor DarkGray
Write-Host ""
