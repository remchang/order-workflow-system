# -*- coding: utf-8 -*-
"""
test_api.py —— 服务与契约测试（实验要求：服务与契约测试 ≥6 条）。

重点不是"接口能返回 200"，而是**状态码和响应体字段符合契约**：
Node-RED 那边要靠状态码分支，字段名要对得上。
"""
import pytest


# ==================== 健康与商品 ====================

def test_jiankang(kehu):
    x = kehu.get("/health")
    assert x.status_code == 200
    ti = x.json()
    assert ti["status"] == "ok"
    assert ti["shangpin_shu"] > 0


def test_shangpin_liebiao_han_ziduan(kehu):
    x = kehu.get("/products")
    assert x.status_code == 200
    sp = x.json()["products"]
    assert len(sp) >= 10, "实验要求至少 10 种商品"
    for z in ("sku", "mingcheng", "leibie", "kucun", "danjia", "danwei"):
        assert z in sp[0]


def test_shangpin_han_san_zhong_kucun_zhuangtai(kehu):
    """种子数据要同时覆盖充足 / 低库存 / 零库存三种情况。"""
    sp = kehu.get("/products").json()["products"]
    ku = [s["kucun"] for s in sp]
    assert max(ku) >= 50, "没有充足库存的商品"
    assert any(0 < k <= 5 for k in ku), "没有低库存的商品"
    assert any(k == 0 for k in ku), "没有零库存的商品"


# ==================== 预留 ====================

def test_yuliu_chenggong_ziduan_wanzheng(kehu):
    x = kehu.post("/reserve", json={"request_id": "A-001", "sku": "A4ZHI", "quantity": 5})
    assert x.status_code == 200
    ti = x.json()
    for z in ("request_id", "sku", "quantity", "shengyu", "zhuangtai", "ok"):
        assert z in ti, z
    assert ti["shengyu"] == 115
    assert ti["chongfu"] is False


def test_yuliu_chongfu_biaoshi(kehu):
    kehu.post("/reserve", json={"request_id": "A-002", "sku": "BOOK", "quantity": 2})
    ti = kehu.post("/reserve", json={"request_id": "A-002", "sku": "BOOK", "quantity": 2}).json()
    assert ti["chongfu"] is True
    assert ti["shengyu"] == 58      # 只扣一次


def test_yuliu_neirong_chongtu_409(kehu):
    kehu.post("/reserve", json={"request_id": "A-003", "sku": "BOOK", "quantity": 2})
    x = kehu.post("/reserve", json={"request_id": "A-003", "sku": "BOOK", "quantity": 9})
    assert x.status_code == 409
    assert x.json()["lei_xing"] == "neirong_chongtu"


def test_yuliu_kucun_buzu_409(kehu):
    x = kehu.post("/reserve", json={"request_id": "A-004", "sku": "TOUYING", "quantity": 1})
    assert x.status_code == 409
    ti = x.json()
    assert ti["lei_xing"] == "kucun_buzu"
    assert ti["kucun_xianyou"] == 0


def test_yuliu_shangpin_bucunzai_404(kehu):
    x = kehu.post("/reserve", json={"request_id": "A-005", "sku": "MEIYOU", "quantity": 1})
    assert x.status_code == 404


@pytest.mark.parametrize("ti", [
    {"request_id": "", "sku": "BOOK", "quantity": 1},
    {"request_id": "A-006", "sku": "", "quantity": 1},
    {"request_id": "A-006", "sku": "BOOK", "quantity": 0},
    {"request_id": "A-006", "sku": "BOOK", "quantity": -2},
    {"request_id": "A-006", "sku": "BOOK", "quantity": "三"},
    {"request_id": "A-006", "sku": "BOOK"},
])
def test_yuliu_canshu_cuowu_400(kehu, ti):
    x = kehu.post("/reserve", json=ti)
    assert x.status_code == 400, ti
    assert x.json()["ok"] is False


def test_yuliu_qingqiuti_feiduixiang_400(kehu):
    """
    请求体不是 JSON 对象时，FastAPI 的类型校验会先拦下来返回 422，
    我们自己的校验（返回 400+中文提示）根本走不到。
    指导书对这个口径写的是"参数错误返回 400 或明确记录的 422"，
    所以这里两种都接受，但必须是其中一种，不能是 200 或 500。
    """
    x = kehu.post("/reserve", json=[1, 2, 3])
    assert x.status_code in (400, 422), x.status_code
    assert x.status_code != 200


# ==================== 查询 ====================

def test_yuliu_liebiao(kehu):
    kehu.post("/reserve", json={"request_id": "A-007", "sku": "BOOK", "quantity": 1})
    ti = kehu.get("/reservations").json()
    assert ti["ok"] is True
    assert any(r["request_id"] == "A-007" for r in ti["reservations"])


def test_yuliu_liebiao_an_zhuangtai_shaixuan(kehu):
    kehu.post("/reserve", json={"request_id": "A-008", "sku": "BOOK", "quantity": 1})
    ti = kehu.get("/reservations?zhuangtai=已完成").json()
    assert ti["zong_shu"] >= 1
    for r in ti["reservations"]:
        assert r["zhuangtai"] == "已完成"

    kong = kehu.get("/reservations?zhuangtai=不存在的状态").json()
    assert kong["zong_shu"] == 0


def test_yuliu_xiangqing(kehu):
    kehu.post("/reserve", json={"request_id": "A-009", "sku": "BOOK", "quantity": 2})
    x = kehu.get("/reservations/A-009")
    assert x.status_code == 200
    assert x.json()["reservation"]["quantity"] == 2


def test_yuliu_xiangqing_weizhi_404(kehu):
    x = kehu.get("/reservations/MEIYOU-ZHEGE")
    assert x.status_code == 404


def test_chaoshi_hou_xian_cha_zai_jueding(kehu):
    """
    ★ 对应指导书"超时意味着结果未知"那条。
    这个测试证明"先查再决定"是可行的：
    未知编号返回 404 → 说明确实没执行 → 可以放心用同一个编号重试。
    """
    x = kehu.get("/reservations/BF-UNKNOWN")
    assert x.status_code == 404

    # 查完确认没执行，再用同一个编号提交，应该成功
    x2 = kehu.post("/reserve", json={
        "request_id": "BF-UNKNOWN", "sku": "BOOK", "quantity": 1})
    assert x2.status_code == 200


# ==================== 规则（自主功能） ====================

def test_guize_duqu_moren(kehu):
    ti = kehu.get("/rules").json()
    assert ti["ok"] is True
    assert ti["guize"]["banben"] == "v1"


def test_baocun_guize_ranhou_shengxiao(kehu):
    x = kehu.post("/rules?banben=v2&meilei_zuida=100&danci_zuida=2")
    assert x.status_code == 200
    assert x.json()["guize"]["danci_zuida"] == 2

    # 按最新规则，单次 3 件应该被拒
    x2 = kehu.post("/reserve", json={"request_id": "A-010", "sku": "BOOK", "quantity": 3})
    assert x2.status_code == 409
    assert x2.json()["lei_xing"] == "guize_chao_xian"

    # 单次 2 件可以
    x3 = kehu.post("/reserve", json={"request_id": "A-011", "sku": "BOOK", "quantity": 2})
    assert x3.status_code == 200


def test_baocun_guize_canshu_feifa(kehu):
    assert kehu.post("/rules?banben=v3&meilei_zuida=0&danci_zuida=5").status_code == 400
    assert kehu.post("/rules?banben=v3&meilei_zuida=10&danci_zuida=-1").status_code == 400


def test_guize_jujue_bu_dong_kucun(kehu):
    """被规则拒掉时不能动库存——校验必须在扣减之前。"""
    kehu.post("/rules?banben=v4&meilei_zuida=100&danci_zuida=2")
    qian = kehu.get("/products").json()["products"]
    qian_ku = [p["kucun"] for p in qian if p["sku"] == "BOOK"][0]

    kehu.post("/reserve", json={"request_id": "A-012", "sku": "BOOK", "quantity": 9})

    hou_ku = [p["kucun"] for p in kehu.get("/products").json()["products"]
              if p["sku"] == "BOOK"][0]
    assert hou_ku == qian_ku, "被规则拒绝的请求改了库存！"
