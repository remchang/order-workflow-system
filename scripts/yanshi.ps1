<#
============================================================
 yanshi.ps1 —— 跑一遍 6 条演示申请

 指导书要求的"至少 6 条正常/异常申请"就是这 6 条。
 每条都会打印请求、期望结果和实际结果，方便对着 PPT 讲。

 前置：两个服务已经用 .\scripts\qidong.ps1 起来了。
============================================================
#>
$ErrorActionPreference = "Continue"

$FlowUrl = "http://127.0.0.1:1880"

$yongli = @(
    @{ bh = "SY-001"; sku = "A4ZHI";    sl = 5;  yuqi = "200 正常" },
    @{ bh = "SY-002"; sku = "SHUBIAO";  sl = 2;  yuqi = "200 正常（低库存但够）" },
    @{ bh = "SY-003"; sku = "TOUYING";  sl = 1;  yuqi = "409 零库存" },
    @{ bh = "SY-004"; sku = "JIANPAN";  sl = 5;  yuqi = "409 库存不足" },
    @{ bh = "SY-005"; sku = "A4ZHI";    sl = 0;  yuqi = "400 数量非法" },
    @{ bh = "SY-006"; sku = "BUCUNZAI"; sl = 1;  yuqi = "404 商品不存在" }
)

Write-Host "===== 前置检查 =====" -ForegroundColor Cyan
try {
    $null = Invoke-RestMethod "$FlowUrl/health" -TimeoutSec 5
    Write-Host "  流程正常" -ForegroundColor Green
} catch {
    Write-Host "  x Node-RED 没起来，先跑 .\scripts\qidong.ps1" -ForegroundColor Red
    exit 1
}

$tongguo = 0; $shibai = 0
Write-Host ""
Write-Host "===== 6 条演示申请 =====" -ForegroundColor Cyan

foreach ($y in $yongli) {
    $ti = @{ request_id = $y.bh; sku = $y.sku; quantity = $y.sl } | ConvertTo-Json
    $ma = 0; $hui = $null
    try {
        $hui = Invoke-RestMethod -Method Post -Uri "$FlowUrl/api/orders" `
            -ContentType "application/json" -Body $ti -TimeoutSec 10
        $ma = 200
    } catch {
        if ($_.Exception.Response) {
            $ma = [int]$_.Exception.Response.StatusCode
            try {
                $du = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $hui = $du.ReadToEnd() | ConvertFrom-Json
            } catch { }
        }
    }

    # 期望的第一个数字就是状态码
    $yuqiMa = [int]($y.yuqi.Split(" ")[0])
    $ok = ($ma -eq $yuqiMa)
    if ($ok) { $tongguo++ } else { $shibai++ }

    $yanse = "Green"; if (-not $ok) { $yanse = "Red" }
    Write-Host ("  [{0}] {1}  {2} × {3}" -f $(if ($ok) { "PASS" } else { "FAIL" }), $y.bh, $y.sku, $y.sl) -ForegroundColor $yanse
    Write-Host ("        期望 {0}  实际 {1}" -f $y.yuqi, $ma)
    if ($hui -and $hui.xiaoxi) { Write-Host ("        说明：{0}" -f $hui.xiaoxi) }
}

Write-Host ""
Write-Host "===== 幂等测试（同一个编号再提交一次）=====" -ForegroundColor Cyan
$ti2 = @{ request_id = "SY-001"; sku = "A4ZHI"; quantity = 5 } | ConvertTo-Json
try {
    $hui2 = Invoke-RestMethod -Method Post -Uri "$FlowUrl/api/orders" `
        -ContentType "application/json" -Body $ti2 -TimeoutSec 10
    if ($hui2.chongfu -eq $true) {
        Write-Host "  [PASS] 识别为幂等命中，库存没有重复扣减" -ForegroundColor Green
        $tongguo++
    } else {
        Write-Host "  [FAIL] 没有标记 chongfu，可能重复扣减了" -ForegroundColor Red
        $shibai++
    }
    Write-Host ("        剩余库存：{0}" -f $hui2.shengyu)
} catch {
    Write-Host "  [FAIL] 请求出错：$($_.Exception.Message)" -ForegroundColor Red
    $shibai++
}

Write-Host ""
Write-Host "===== 结果 =====" -ForegroundColor Cyan
Write-Host ("  通过 {0} 项，失败 {1} 项" -f $tongguo, $shibai) -ForegroundColor $(if ($shibai -eq 0) { "Green" } else { "Red" })
Write-Host ""
Write-Host "  看记录列表： http://127.0.0.1:1880/orders.html"
Write-Host "  看异常记录： http://127.0.0.1:1880/api/yichang"
