# -*- coding: utf-8 -*-
"""
app.py —— 库存服务（FastAPI）。

数据所有权说明（本实验的核心边界）：
    · 库存和预留记录**只属于这个服务**；
    · Node-RED 只能通过 HTTP 调这里，**不能**直接读写 kucun.db；
    · 只有本进程会打开那个 SQLite 文件。

接口清单：
    GET  /health                        健康检查
    GET  /products                      商品列表（前端展示真实库存）
    POST /reserve                       预留库存（幂等 + 事务）
    GET  /reservations                  预留记录列表（可按状态筛选）
    GET  /reservations/{request_id}     按编号查详情（超时后先查再重试就靠它）
    GET  /rules                         当前规则版本
    POST /rules                         保存一个新规则版本（自主功能）

状态码约定：
    400 参数错误
    404 商品或记录不存在
    409 业务冲突（库存不足 / 编号内容冲突）
    422 FastAPI 自带的请求体校验失败（字段类型不对）
    503 依赖不可用（数据库被锁等）
"""
import os
import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import kucun
from zhongzi import SHANGPIN_LIEBIAO

# 数据库路径：允许用环境变量覆盖，方便测试用临时库
KU_LUJING = os.environ.get("KUCUN_DB", kucun.MOREN_KU_LUJING)

app = FastAPI(
    title="库存服务",
    description="实验06 的独立库存服务。库存与预留记录只归本服务所有。",
    version="1.0.0",
)


@app.on_event("startup")
def qidong_shihou():
    """启动时建表并灌种子数据。种子是幂等的，重复启动不会覆盖已有库存。"""
    kucun.chushihua_zhongzi(KU_LUJING, SHANGPIN_LIEBIAO)
    # 默认规则版本：单次最多 20，单类累计最多 200
    if kucun.chaxun_guize(KU_LUJING) is None:
        kucun.baocun_guize(KU_LUJING, "v1", meilei_zuida=200, danci_zuida=20)


# ---------------- 统一异常处理 ----------------

@app.exception_handler(kucun.KucunCuowu)
async def kucun_cuowu_chuli(request: Request, e: kucun.KucunCuowu):
    """
    把业务异常翻译成 JSON。错误体统一带 ok/laiyuan/xiaoxi，
    让 Node-RED 那边好分支（它要按状态码区分业务拒绝和依赖故障）。
    """
    ti = {
        "ok": False,
        "laiyuan": "kucun-fuwu",
        "xiaoxi": e.xiaoxi,
    }
    ti.update(e.qita)
    return JSONResponse(status_code=e.zhuangtai_ma, content=ti)


@app.exception_handler(sqlite3.OperationalError)
async def shuju_cuowu_chuli(request: Request, e: Exception):
    """
    数据库被锁或不可用 → 503。
    ★ 这一点很重要：依赖不可用时**必须**返回 5xx，
    不能让 Node-RED 把它当成业务拒绝，更不能伪造成功。
    """
    return JSONResponse(
        status_code=503,
        content={
            "ok": False,
            "laiyuan": "kucun-fuwu",
            "xiaoxi": "数据库暂时不可用：%s" % e,
        },
    )


# ---------------- 健康与查询 ----------------

@app.get("/health")
def jiankang():
    """健康检查。顺带确认一下数据库能打开，不然"活着"没意义。"""
    try:
        shu = len(kucun.chaxun_shangpin(KU_LUJING))
        return {"status": "ok", "shangpin_shu": shu, "ku": os.path.basename(KU_LUJING)}
    except Exception as e:                      # noqa: BLE001
        return JSONResponse(
            status_code=503,
            content={"status": "bad", "xiaoxi": str(e)},
        )


@app.get("/products")
def shangpin_liebiao():
    return {"ok": True, "products": kucun.chaxun_shangpin(KU_LUJING)}


@app.get("/rules")
def dangqian_guize():
    gz = kucun.chaxun_guize(KU_LUJING)
    return {"ok": True, "guize": gz}


@app.post("/rules")
def baocun_guize(banben: str, meilei_zuida: int, danci_zuida: int):
    """
    保存规则版本（自主功能）。

    每次修改都产生一个新版本号，历史记录里保存的是"当时用的哪个版本"。
    为什么要版本：规则改过之后，事后审计必须能说清
    "这笔申请当时是按哪一版规则通过的"。没有版本号就是一锅粥。
    """
    if meilei_zuida <= 0 or danci_zuida <= 0:
        return JSONResponse(status_code=400, content={
            "ok": False, "xiaoxi": "上限必须大于 0"})
    gz = kucun.baocun_guize(KU_LUJING, banben, meilei_zuida, danci_zuida)
    return {"ok": True, "guize": gz}


@app.get("/reservations")
def yuliu_liebiao(zhuangtai: str = None, zuiduo: int = 200):
    hang = kucun.chaxun_yuliu(KU_LUJING, zhuangtai=zhuangtai, zuiduo=zuiduo)
    return {"ok": True, "reservations": hang, "zong_shu": len(hang)}


@app.get("/reservations/{request_id}")
def yuliu_xiangqing(request_id: str):
    hang = kucun.chaxun_yuliu(KU_LUJING, request_id=request_id)
    if not hang:
        # ★ 未知编号返回 404。超时后"先查再决定重试"就依赖这个接口。
        return JSONResponse(status_code=404, content={
            "ok": False, "laiyuan": "kucun-fuwu",
            "xiaoxi": "没有找到编号 %s 的预留记录" % request_id})
    return {"ok": True, "reservation": hang[0]}


@app.post("/reserve")
def yuliu_shiti(ti: dict):
    """
    预留库存。请求体：
        {"request_id":"s2026001-001","sku":"BOOK","quantity":2}

    这里先用 dict 接，再自己校验，是为了让 400 的错误信息统一成中文
    并且和 kucun.py 的校验逻辑共用一套（避免两处规则不一致）。
    FastAPI 的 Pydantic 校验留给字段类型明显不对的情况（返回 422）。
    """
    if not isinstance(ti, dict):
        return JSONResponse(status_code=400, content={
            "ok": False, "laiyuan": "kucun-fuwu", "xiaoxi": "请求体必须是 JSON 对象"})

    request_id = ti.get("request_id")
    sku = ti.get("sku")
    quantity = ti.get("quantity")

    # 字段白名单：多传的字段忽略但不报错（方便以后加字段）
    if request_id is None or str(request_id).strip() == "":
        return JSONResponse(status_code=400, content={
            "ok": False, "laiyuan": "kucun-fuwu", "xiaoxi": "request_id 不能为空"})
    if sku is None or str(sku).strip() == "":
        return JSONResponse(status_code=400, content={
            "ok": False, "laiyuan": "kucun-fuwu", "xiaoxi": "sku 不能为空"})
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        return JSONResponse(status_code=400, content={
            "ok": False, "laiyuan": "kucun-fuwu", "xiaoxi": "quantity 必须是整数"})
    if quantity <= 0:
        return JSONResponse(status_code=400, content={
            "ok": False, "laiyuan": "kucun-fuwu", "xiaoxi": "quantity 必须大于 0"})

    # 自主功能：先按规则版本校验上限。
    # ★ 放在真正扣减之前——被规则拒绝的请求不该动库存。
    tongguo, guize_banben, shuoming = kucun.jiancha_guize(KU_LUJING, sku, quantity)
    if not tongguo:
        return JSONResponse(status_code=409, content={
            "ok": False, "laiyuan": "kucun-fuwu",
            "xiaoxi": shuoming, "lei_xing": "guize_chao_xian",
            "guize_banben": guize_banben})

    zhuangtai, jieguo = kucun.yuliuku_cun(
        KU_LUJING, request_id, sku, quantity, guize_banben=guize_banben
    )
    jieguo["ok"] = True
    jieguo["laiyuan"] = "kucun-fuwu"
    jieguo["guize_banben"] = guize_banben
    return jieguo


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
