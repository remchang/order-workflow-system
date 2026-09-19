<#
============================================================
 tingzhi.ps1 —— 停止两个进程

 只杀本项目起的 python / node 进程，按端口定位，不用进程名全杀
 （否则会误伤用户其他的 python/node 程序）。
============================================================
#>
param(
    [int[]]$Duankou = @(8001, 1880)
)

$ErrorActionPreference = "Continue"

Write-Host "==> 按端口停止进程" -ForegroundColor Cyan
foreach ($dk in $Duankou) {
    $zhan = Get-NetTCPConnection -LocalPort $dk -State Listen -ErrorAction SilentlyContinue
    if (-not $zhan) {
        Write-Host "  端口 $dk 没有监听，跳过"
        continue
    }
    foreach ($pid_ in ($zhan | Select-Object -ExpandProperty OwningProcess -Unique)) {
        $jc = Get-Process -Id $pid_ -ErrorAction SilentlyContinue
        if ($jc) {
            Write-Host "  停掉 $($jc.ProcessName) (PID $pid_)，占用端口 $dk"
            Stop-Process -Id $pid_ -Force -ErrorAction SilentlyContinue
        }
    }
}

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "==> 确认" -ForegroundColor Cyan
foreach ($dk in $Duankou) {
    $zhan = Get-NetTCPConnection -LocalPort $dk -State Listen -ErrorAction SilentlyContinue
    if ($zhan) { Write-Host "  ! 端口 $dk 还在监听" -ForegroundColor Yellow }
    else { Write-Host "  端口 $dk 已释放" -ForegroundColor Green }
}

Write-Host ""
Write-Host "注意：数据库文件 data\kucun.db 没有被删。" -ForegroundColor Green
Write-Host "      下次启动时库存和预留记录都还在。" -ForegroundColor Green
Write-Host "      要清空数据请跑 .\scripts\zhongzhi.ps1 -Chongjian" -ForegroundColor Yellow
