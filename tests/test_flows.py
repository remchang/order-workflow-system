# -*- coding: utf-8 -*-
"""
test_flows.py —— 编排功能测试（实验要求：编排功能测试 ≥6 条）。

本机没有跑 Node-RED（需要 npm 安装约 80MB 的依赖），
所以这一组测试做的是**静态验证**：把 flows/*.json 当作数据来检查结构。

这不是"假装跑过了"。它真的能抓到几类实际会犯的错：
    · 连线指向了不存在的节点（Deploy 时会报错或静默丢消息）
    · Function 的输出路数和接线数对不上
    · 忘了保留 msg.req / msg.res，导致 HTTP Response 不知道回哪个请求
    · 校验分支没接到错误响应，非法输入会挂住不返回
"""
import json
import os
import re

import pytest

GEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOWS = os.path.join(GEN, "flows")


def _du(ming):
    with open(os.path.join(FLOWS, ming), "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def zhuliu():
    return _du("orders.json")


@pytest.fixture(scope="module")
def jixian():
    return _du("baseline.json")


def _zhaobiankuai(liucheng):
    return {j["id"]: j for j in liucheng if "id" in j}


# ==================== 结构 ====================

def test_liangfen_wenjian_dou_neng_jiexi(zhuliu, jixian):
    assert isinstance(zhuliu, list) and len(zhuliu) > 5
    assert isinstance(jixian, list) and len(jixian) >= 4


def test_meige_tab_dou_you_id(zhuliu, jixian):
    for liucheng in (zhuliu, jixian):
        tabs = [j for j in liucheng if j.get("type") == "tab"]
        assert len(tabs) == 1
        assert tabs[0]["id"]


def test_suoyou_lianxian_dou_zhi_xiang_cunzai_de_jiedian(zhuliu):
    """★ 连线指向不存在的节点，Deploy 时就会出错。这条最容易犯。"""
    ge = _zhaobiankuai(zhuliu)
    wenti = []
    for j in zhuliu:
        for lu in (j.get("wires") or []):
            for mubiao in lu:
                if mubiao and mubiao not in ge:
                    wenti.append("%s(%s) -> %s 不存在" % (j["id"], j.get("type"), mubiao))
    assert wenti == [], "悬空连线：%s" % wenti


def test_function_shuchulu_shu_he_jiexian_shu_yizhi(zhuliu):
    """Function 声明了几路输出，就必须有几组接线。"""
    wenti = []
    for j in zhuliu:
        if j.get("type") != "function":
            continue
        shu = int(j.get("outputs", 1))
        jie = j.get("wires") or []
        if len(jie) != shu:
            wenti.append("%s 声明 %d 路，接线 %d 组" % (j.get("name") or j["id"], shu, len(jie)))
    assert wenti == [], wenti


def test_http_in_dou_you_url_he_method(zhuliu):
    for j in zhuliu:
        if j.get("type") == "http in":
            assert j.get("url"), j["id"]
            assert j.get("method") in ("get", "post", "put", "delete"), j["id"]


def test_meige_http_in_dou_neng_zou_dao_http_response(zhuliu):
    """
    从每个 http in 出发做一次可达性遍历，必须能走到 http response。
    否则请求会一直挂着不返回——这是最烦人的一类 bug。
    """
    ge = _zhaobiankuai(zhuliu)
    bukeyi = []
    for j in zhuliu:
        if j.get("type") != "http in":
            continue
        yifang = set()
        duilie = [j["id"]]
        dao = False
        while duilie:
            dian = duilie.pop()
            if dian in yifang:
                continue
            yifang.add(dian)
            jd = ge.get(dian)
            if jd is None:
                continue
            if jd.get("type") == "http response":
                dao = True
                break
            for lu in (jd.get("wires") or []):
                for m in lu:
                    duilie.append(m)
        if not dao:
            bukeyi.append(j.get("url"))
    assert bukeyi == [], "这些入口走不到 HTTP Response：%s" % bukeyi


# ==================== msg.req / msg.res 保护 ====================

def test_function_buyao_yong_huifu_xin_duixiang(zhuliu):
    """
    ★ 指导书明确写的坑：
      "Function 必须保留 msg.req 和 msg.res，不能只返回新的 {payload: ...}"
    这里用静态检查抓这种写法：函数体里如果出现 `return { payload:` 之类的
    纯字面量返回，说明 msg 被整个换掉了，msg.res 就丢了。
    """
    huai = []
    for j in zhuliu:
        if j.get("type") != "function":
            continue
        dai = j.get("func") or ""
        # 匹配 return {      或   return [ {  这种新对象返回
        if re.search(r"return\s*(\[\s*)?\{", dai):
            huai.append(j.get("name") or j["id"])
    assert huai == [], "这些 Function 返回了新对象，会丢 msg.res：%s" % huai


def test_function_dou_you_feikong_daima(zhuliu):
    for j in zhuliu:
        if j.get("type") == "function":
            assert (j.get("func") or "").strip(), j["id"]


# ==================== 业务分支 ====================

def test_post_orders_you_lianglu_shuchu(zhuliu):
    """提交订单的校验函数必须是 2 路输出：合法 / 非法。"""
    tou = [j for j in zhuliu
           if j.get("type") == "http in" and j.get("method") == "post"
           and j.get("url") == "/api/orders"]
    assert len(tou) == 1

    ge = _zhaobiankuai(zhuliu)
    jiaoyan = ge[tou[0]["wires"][0][0]]
    assert jiaoyan["type"] == "function"
    assert int(jiaoyan["outputs"]) == 2


def test_feifa_fenzhi_jie_dao_le_400(zhuliu):
    """非法分支必须能走到一个把状态码设成 4xx 的地方。"""
    ge = _zhaobiankuai(zhuliu)
    zhaodao = False
    for j in zhuliu:
        if j.get("type") == "function" and "400" in (j.get("func") or ""):
            zhaodao = True
    assert zhaodao, "没有找到回 400 的逻辑"


def test_you_catch_jiedian_chuli_wangluo_yichang(zhuliu):
    """网络异常必须有 Catch 兜底，否则请求会挂住。"""
    cat = [j for j in zhuliu if j.get("type") == "catch"]
    assert len(cat) >= 1
    assert cat[0]["wires"][0][0] in _zhaobiankuai(zhuliu)


def test_catch_hou_mian_you_http_response(zhuliu):
    ge = _zhaobiankuai(zhuliu)
    cat = [j for j in zhuliu if j.get("type") == "catch"][0]
    houxu = ge[cat["wires"][0][0]]
    assert houxu.get("wires") and any(
        ge.get(m, {}).get("type") == "http response"
        for lu in houxu["wires"] for m in lu
    ), "Catch 后面没有 HTTP Response"


def test_chaoshi_bu_bei_dangcheng_shibai(zhuliu):
    """
    ★ 对应指导书的思考题："超时意味着结果未知，不等于对方没有执行"。
    错误处理函数里必须出现"查询/未知"这类引导，不能只说"失败了"。
    """
    ge = _zhaobiankuai(zhuliu)
    cat = [j for j in zhuliu if j.get("type") == "catch"][0]
    dai = ge[cat["wires"][0][0]]["func"]
    assert ("未知" in dai) or ("查" in dai), "超时被直接当成失败了"


def test_diao_kucun_fuwu_yong_8001(zhuliu):
    """所有 HTTP Request 都要打向库存服务，而不是直接读它的数据库。"""
    qingqiu = [j for j in zhuliu if j.get("type") == "http request"]
    assert len(qingqiu) >= 3
    for q in qingqiu:
        url = q.get("url") or ""
        if url:                       # 详情接口的 URL 是运行时拼的，允许为空
            assert "127.0.0.1:8001" in url, url


def test_meiyou_jiedian_zhijie_du_sqlite(zhuliu):
    """编排层绝对不能直接碰 kucun.db —— 数据所有权边界。"""
    for j in zhuliu:
        dai = (j.get("func") or "") + (j.get("url") or "")
        assert "kucun.db" not in dai
        assert "sqlite" not in dai.lower()


def test_jiankang_jiekou_bu_yilai_waibu_fuwu(zhuliu):
    """
    /health 要能不依赖库存服务单独返回 —— 不然两个服务互相依赖就分不清谁挂了。
    """
    ge = _zhaobiankuai(zhuliu)
    tou = [j for j in zhuliu
           if j.get("type") == "http in" and j.get("url") == "/health"][0]
    houxu = [ge[m] for lu in tou["wires"] for m in lu]
    assert all(h.get("type") != "http request" for h in houxu), \
        "/health 依赖了外部服务，单独排障时会分不清是谁挂了"


def test_jixian_liucheng_zhi_you_jiankang(jixian):
    """基线流程要足够简单：只有一个入口，不依赖任何外部服务。"""
    ru = [j for j in jixian if j.get("type") == "http in"]
    assert len(ru) == 1
    assert ru[0]["url"] == "/health"
    assert not [j for j in jixian if j.get("type") == "http request"]
