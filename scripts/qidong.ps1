<#
============================================================
 qidong.ps1 —— 一键启动两个进程

 顺序很重要：**先起库存服务，再起 Node-RED**。
 反过来的话，Node-RED 一起来就去调库存服务会拿到连接拒绝，
 虽然不会崩，但日志里会有一串难看的错误，误导排障。

 两个进程的日志分别写到 logs\kucun.log 和 logs\node-red.log。
============================================================
#>
param(
    [int]$KucunDuankou = 8001,
    [int]$FlowDuankou = 1880
)

$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force -Path "logs", "data" | Out-Null

Write-Host "===== ① 检查 .venv 和 node_modules =====" -ForegroundColor Cyan
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "  x 没有 .venv，先跑 .\scripts\anzhuang.ps1" -ForegroundColor Red; exit 1
}
if (-not (Test-Path "node_modules\node-red\red.js")) {
    Write-Host "  x 没有装 node-red，先跑 .\scripts\anzhuang.ps1" -ForegroundColor Red; exit 1
}

Write-Host ""
Write-Host "===== ② 启动库存服务（:$KucunDuankou）=====" -ForegroundColor Cyan
$huanjing = @{ KUCUN_DB = (Join-Path (Get-Location) "data\kucun.db") }
$kucunJincheng = Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "$KucunDuankou" `
    -WorkingDirectory (Join-Path (Get-Location) "service") `
    -RedirectStandardOutput "logs\kucun.log" -RedirectStandardError "logs\kucun-err.log" `
    -PassThru -WindowStyle Hidden

# 等健康检查，不靠固定 sleep
$shangxian = (Get-Date).AddSeconds(40)
$hao = $false
while ((Get-Date) -lt $shangxian) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-RestMethod "http://127.0.0.1:$KucunDuankou/health" -TimeoutSec 3
        if ($r.status -eq "ok") { $hao = $true; break }
    } catch { }
}
if ($hao) {
    Write-Host "  库存服务就绪（商品 $($r.shangpin_shu) 种）" -ForegroundColor Green
} else {
    Write-Host "  ! 库存服务 40 秒内没就绪，看 logs\kucun-err.log" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "===== ③ 启动 Node-RED（:$FlowDuankou）=====" -ForegroundColor Cyan
$flowJincheng = Start-Process -FilePath "node" `
    -ArgumentList "node_modules\node-red\red.js", "--userDir", ".\data\node-red", "--settings", ".\settings.js", ".\flows\orders.json" `
    -WorkingDirectory (Get-Location) `
    -RedirectStandardOutput "logs\node-red.log" -RedirectStandardError "logs\node-red-err.log" `
    -PassThru -WindowStyle Hidden

$shangxian = (Get-Date).AddSeconds(60)
$hao2 = $false
while ((Get-Date) -lt $shangxian) {
    Start-Sleep -Seconds 2
    try {
        $r2 = Invoke-RestMethod "http://127.0.0.1:$FlowDuankou/health" -TimeoutSec 3
        if ($r2.status -eq "ok") { $hao2 = $true; break }
    } catch { }
}
if ($hao2) {
    Write-Host "  流程就绪" -ForegroundColor Green
} else {
    Write-Host "  ! Node-RED 60 秒内没就绪，看 logs\node-red.log" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "===== 启动完成 =====" -ForegroundColor Green
Write-Host "  操作页面    http://127.0.0.1:$FlowDuankou/orders.html"
Write-Host "  流程编辑器  http://127.0.0.1:$FlowDuankou/editor"
Write-Host "  库存服务文档 http://127.0.0.1:$KucunDuankou/docs"
Write-Host ""
Write-Host "  进程号：库存=$($kucunJincheng.Id)  Node-RED=$($flowJincheng.Id)"
Write-Host "  停止用  .\scripts\tingzhi.ps1"
Write-Host ""
Write-Host "  跑一遍演示用例：.\scripts\yanshi.ps1" -ForegroundColor Cyan
