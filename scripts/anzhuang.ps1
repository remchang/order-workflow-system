<#
============================================================
 anzhuang.ps1 —— 一键安装

 做三件事：
   ① 建 Python 虚拟环境并装库存服务的依赖
   ② 装 Node-RED（固定 5.0.7，装到项目本地，不做全局安装）
   ③ 跑一遍测试确认装对了

 为什么要指定镜像：直连 PyPI 经常超时（实测约 100 KB/s 且会断），
 用国内镜像稳定得多。不需要可以去掉 -Jingxiang 参数。
============================================================
#>
param(
    [string]$Jingxiang = "https://mirrors.aliyun.com/pypi/simple/"
)

$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "===== ① 检查 Node / Python =====" -ForegroundColor Cyan
$nodeBanben = (node --version)
Write-Host "  Node:   $nodeBanben"
Write-Host "  Python: $((python --version) 2>&1)"

# Node-RED 5.0.7 要求 Node >= 22.9
$zhu = [int]($nodeBanben.TrimStart('v').Split('.')[0])
$ci = [int]($nodeBanben.TrimStart('v').Split('.')[1])
if ($zhu -lt 22 -or ($zhu -eq 22 -and $ci -lt 9)) {
    Write-Host "  x Node-RED 5.0.7 需要 Node 22.9 以上，当前是 $nodeBanben" -ForegroundColor Red
    Write-Host "    请不要用忽略 engines 的方式硬装，先升级 Node。" -ForegroundColor Red
    exit 1
}
Write-Host "  Node 版本满足要求" -ForegroundColor Green

Write-Host ""
Write-Host "===== ② Python 虚拟环境 =====" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    python -m venv .venv
    Write-Host "  已创建 .venv"
} else {
    Write-Host "  .venv 已存在"
}
& ".\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check `
    --upgrade pip -i $Jingxiang --trusted-host ([Uri]$Jingxiang).Host | Out-Null
& ".\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check `
    -r "service\requirements.txt" -i $Jingxiang --trusted-host ([Uri]$Jingxiang).Host
if ($LASTEXITCODE -ne 0) { Write-Host "  x Python 依赖安装失败" -ForegroundColor Red; exit 1 }
Write-Host "  Python 依赖装好了" -ForegroundColor Green

Write-Host ""
Write-Host "===== ③ Node-RED（项目本地安装，不用 -g）=====" -ForegroundColor Cyan
if (-not (Test-Path "package-lock.json")) {
    npm install --save-exact node-red@5.0.7 --registry=https://registry.npmmirror.com
} else {
    Write-Host "  已有锁定文件，用 npm ci 装（可复现）"
    npm ci --registry=https://registry.npmmirror.com
}
if ($LASTEXITCODE -ne 0) { Write-Host "  x Node-RED 安装失败" -ForegroundColor Red; exit 1 }
Write-Host "  Node-RED 装好了" -ForegroundColor Green

Write-Host ""
Write-Host "===== ④ 跑测试确认 =====" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m pytest tests -q
Write-Host ""
Write-Host "安装完成。启动：" -ForegroundColor Green
Write-Host "  .\scripts\qidong.ps1"
