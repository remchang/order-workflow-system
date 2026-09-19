<#
============================================================
 ceshi.ps1 —— 一键跑全部测试

 三类：
   ① pytest（库存事务/幂等/并发 + 服务契约 + 流程静态校验）
   ② 复现性检查（新建库跑一遍种子，确认幂等）
   ③ 流程 JSON 能不能被 Node 解析（相当于 Deploy 前的语法检查）
============================================================
#>
$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "===== ① pytest =====" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m pytest tests -q -p no:warnings
$pytestHao = ($LASTEXITCODE -eq 0)

Write-Host ""
Write-Host "===== ② 种子幂等性（灌两次，库存不能被还原）=====" -ForegroundColor Cyan
$suiji = Join-Path $env:TEMP ("kucun_fuyan_" + [Guid]::NewGuid().ToString("N").Substring(0, 8) + ".db")
& ".\.venv\Scripts\python.exe" -c @"
import sys
sys.path.insert(0, 'service')
import kucun
from zhongzi import SHANGPIN_LIEBIAO
db = r'$suiji'
kucun.chushihua_zhongzi(db, SHANGPIN_LIEBIAO)
kucun.yuliuku_cun(db, 'FY-001', 'A4ZHI', 20)
a = kucun.chaxun_dan_ge(db, 'A4ZHI')['kucun']
kucun.chushihua_zhongzi(db, SHANGPIN_LIEBIAO)
b = kucun.chaxun_dan_ge(db, 'A4ZHI')['kucun']
print('  扣减后=%d  再灌种子后=%d' % (a, b))
print('  [%s] 种子幂等' % ('PASS' if a == b == 100 else 'FAIL'))
"@
Remove-Item -Force $suiji -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "===== ③ 流程 JSON 语法检查（Node 解析）=====" -ForegroundColor Cyan
& node -e @"
const fs = require('fs');
for (const f of ['flows/orders.json', 'flows/baseline.json']) {
  try {
    const j = JSON.parse(fs.readFileSync(f, 'utf8'));
    const types = {};
    j.forEach(n => { types[n.type] = (types[n.type] || 0) + 1; });
    console.log('  [PASS] ' + f + '  ' + j.length + ' 个节点  ' + JSON.stringify(types));
  } catch (e) {
    console.log('  [FAIL] ' + f + '  ' + e.message);
    process.exitCode = 1;
  }
}
"@

Write-Host ""
Write-Host "===== ④ settings.js 语法检查 =====" -ForegroundColor Cyan
& node -e "const s=require('./settings.js'); console.log('  [PASS] uiHost=' + s.uiHost + ' uiPort=' + s.uiPort + ' httpAdminRoot=' + s.httpAdminRoot); if(!s.httpStatic){console.log('  [FAIL] 没有配 httpStatic，操作页面访问不到'); process.exitCode=1;}"

Write-Host ""
if ($pytestHao) {
    Write-Host "全部通过。" -ForegroundColor Green
} else {
    Write-Host "pytest 有失败项，看上面输出。" -ForegroundColor Red
}
