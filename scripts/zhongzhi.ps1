<#
============================================================
 zhongzhi.ps1 —— 初始化 / 重建演示数据

 默认行为：**幂等**地灌种子（已存在的商品不动库存）。
           这是刻意的——反复跑种子脚本不能把测试中扣掉的库存还原，
           否则证据就没了。

 -Chongjian 才会删掉数据库重建。这是破坏性操作，要手打确认。
============================================================
#>
param(
    [switch]$Chongjian
)

$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)

$Ku = Join-Path (Get-Location) "data\kucun.db"
New-Item -ItemType Directory -Force -Path "data" | Out-Null

if ($Chongjian) {
    Write-Host "⚠️  危险操作：这会删掉 $Ku" -ForegroundColor Yellow
    Write-Host "    里面的库存扣减和预留记录都会没，且不可恢复。" -ForegroundColor Yellow
    Write-Host "    要保留就先备份： Copy-Item `"$Ku`" `"$Ku.bak`"" -ForegroundColor Yellow
    $q = Read-Host "确认请输入 删除数据库"
    if ($q -ne "删除数据库") {
        Write-Host "已取消。" -ForegroundColor Green
        exit 0
    }
    # 连 WAL / SHM 一起删，不然会残留半截事务
    foreach ($h in @("", "-wal", "-shm")) {
        Remove-Item -Force "$Ku$h" -ErrorAction SilentlyContinue
    }
    Write-Host "已删除。" -ForegroundColor Green
}

Write-Host "==> 灌入种子数据" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -c @"
import sys
sys.path.insert(0, 'service')
import kucun
from zhongzi import SHANGPIN_LIEBIAO
db = r'$Ku'
hang = kucun.chushihua_zhongzi(db, SHANGPIN_LIEBIAO)
print('  商品 %d 种' % len(hang))
chong = sum(1 for h in hang if h['kucun'] == 0)
di = sum(1 for h in hang if 0 < h['kucun'] <= 5)
print('  充足 %d / 低库存 %d / 零库存 %d' % (len(hang) - chong - di, di, chong))
gz = kucun.chaxun_guize(db)
if gz is None:
    kucun.baocun_guize(db, 'v1', meilei_zuida=200, danci_zuida=20)
    gz = kucun.chaxun_guize(db)
print('  当前规则版本 %s（单类累计上限 %d，单次上限 %d）' % (gz['banben'], gz['meilei_zuida'], gz['danci_zuida']))
"@
if ($LASTEXITCODE -ne 0) { Write-Host "  x 失败" -ForegroundColor Red; exit 1 }
Write-Host "  完成。数据库：$Ku" -ForegroundColor Green
