# -*- coding: utf-8 -*-
"""
test_kucun.py —— 库存与幂等测试（实验要求：库存与幂等测试 ≥5 条）。

这一组是本实验最核心的测试。要证明三件事：
    ① 同一编号不重复扣减
    ② 同号不同内容能识别出来
    ③ 并发下不超卖、不出现负库存
"""
import threading

import pytest

import kucun


# ==================== 基本事务 ====================

def test_yuliu_chenggong_bing_koujian(ku):
    zhuangtai, jieguo = kucun.yuliuku_cun(ku, "T-001", "A4ZHI", 5)
    assert zhuangtai == "xinjian"
    assert jieguo["shengyu"] == 115          # 120 - 5
    assert jieguo["chongfu"] is False
    assert kucun.chaxun_dan_ge(ku, "A4ZHI")["kucun"] == 115


def test_tongyibianhao_buchongfu_koujian(ku):
    """★ 幂等：同一编号 + 同样内容，第二次不扣减，直接返回原结果。"""
    kucun.yuliuku_cun(ku, "T-002", "BOOK", 3)
    zhuangtai, jieguo = kucun.yuliuku_cun(ku, "T-002", "BOOK", 3)

    assert zhuangtai == "chongfu"
    assert jieguo["chongfu"] is True
    # 库存只能被扣一次
    assert kucun.chaxun_dan_ge(ku, "BOOK")["kucun"] == 57   # 60 - 3
    # 预留记录也只有一条
    assert len(kucun.chaxun_yuliu(ku, request_id="T-002")) == 1


def test_tongyibianhao_butong_neirong_baocuo(ku):
    """
    ★ 编号绑内容：同号但数量不同 → 409 冲突，不能静默当成重复请求。
    如果没有这一条，调用方会以为自己的新请求被处理了，其实数据没动。
    """
    kucun.yuliuku_cun(ku, "T-003", "BOOK", 3)
    with pytest.raises(kucun.KucunCuowu) as e:
        kucun.yuliuku_cun(ku, "T-003", "BOOK", 4)
    assert e.value.zhuangtai_ma == 409
    assert e.value.qita.get("lei_xing") == "neirong_chongtu"
    # 冲突的请求不能改库存
    assert kucun.chaxun_dan_ge(ku, "BOOK")["kucun"] == 57


def test_tongyibianhao_huan_shangpin_yie_chongtu(ku):
    kucun.yuliuku_cun(ku, "T-004", "BOOK", 2)
    with pytest.raises(kucun.KucunCuowu) as e:
        kucun.yuliuku_cun(ku, "T-004", "QIANBI", 2)
    assert e.value.zhuangtai_ma == 409


# ==================== 库存边界 ====================

def test_kucun_buzu_fanhui_409(ku):
    with pytest.raises(kucun.KucunCuowu) as e:
        kucun.yuliuku_cun(ku, "T-005", "JIANPAN", 5)     # 库存只有 1
    assert e.value.zhuangtai_ma == 409
    assert e.value.qita["kucun_xianyou"] == 1
    assert kucun.chaxun_dan_ge(ku, "JIANPAN")["kucun"] == 1   # 没被改动


def test_ling_kucun_buneng_yuliu(ku):
    with pytest.raises(kucun.KucunCuowu) as e:
        kucun.yuliuku_cun(ku, "T-006", "TOUYING", 1)
    assert e.value.zhuangtai_ma == 409


def test_lijie_zhi_ganghao_gou(ku):
    """临界：库存 1，申请 1 → 应该成功，剩余 0，且库存绝不为负。"""
    zhuangtai, jieguo = kucun.yuliuku_cun(ku, "T-007", "JIANPAN", 1)
    assert zhuangtai == "xinjian"
    assert jieguo["shengyu"] == 0
    assert kucun.chaxun_dan_ge(ku, "JIANPAN")["kucun"] == 0


def test_lijie_zhi_cha_yi(ku):
    kucun.yuliuku_cun(ku, "T-008", "JIANPAN", 1)
    with pytest.raises(kucun.KucunCuowu):
        kucun.yuliuku_cun(ku, "T-009", "JIANPAN", 1)


# ==================== 参数与商品 ====================

def test_shangpin_bucunzai_404(ku):
    with pytest.raises(kucun.KucunCuowu) as e:
        kucun.yuliuku_cun(ku, "T-010", "BUCUNZAI", 1)
    assert e.value.zhuangtai_ma == 404


def test_shuliang_feifa_400(ku):
    for huai in (0, -3):
        with pytest.raises(kucun.KucunCuowu) as e:
            kucun.yuliuku_cun(ku, "T-011", "BOOK", huai)
        assert e.value.zhuangtai_ma == 400


def test_bianhao_weikong_400(ku):
    with pytest.raises(kucun.KucunCuowu) as e:
        kucun.yuliuku_cun(ku, "   ", "BOOK", 1)
    assert e.value.zhuangtai_ma == 400


def test_sku_daxiee_guiyihua(ku):
    """sku 大小写不同应视为同一个商品，不能绕过库存。"""
    kucun.yuliuku_cun(ku, "T-012", "book", 3)
    assert kucun.chaxun_dan_ge(ku, "BOOK")["kucun"] == 57


# ==================== 并发 ====================

def test_bingfa_bu_chaomai(ku):
    """
    ★ 并发边界：库存只够一条（QIANBI 是 300，这里用一个临时商品）。
    建一个库存为 3 的商品，两个线程各申请 2 —— 必须恰好一条成功，
    且库存不能为负。
    """
    with kucun._lianjie(ku) as lian:
        lian.execute(
            "INSERT INTO products (sku, mingcheng, leibie, kucun, danjia, danwei) "
            "VALUES ('CESHI','并发测试品','测试',3,1.0,'个')"
        )

    jieguo = []
    suo = threading.Lock()

    def _tou(bianhao):
        try:
            kucun.yuliuku_cun(ku, bianhao, "CESHI", 2)
            with suo:
                jieguo.append("成功")
        except kucun.KucunCuowu as e:
            with suo:
                jieguo.append("失败%d" % e.zhuangtai_ma)

    xian1 = threading.Thread(target=_tou, args=("BF-001",))
    xian2 = threading.Thread(target=_tou, args=("BF-002",))
    xian1.start(); xian2.start(); xian1.join(); xian2.join()

    assert sorted(jieguo) == ["失败409", "成功"], jieguo
    sheng = kucun.chaxun_dan_ge(ku, "CESHI")["kucun"]
    assert sheng == 1, "库存应该是 3-2=1，实际 %s" % sheng
    assert sheng >= 0, "库存出现负数，说明条件更新没起作用"


def test_bingfa_tongyibianhao_zhi_kou_yici(ku):
    """两个线程提交完全相同的请求 → 库存只扣一次。"""
    with kucun._lianjie(ku) as lian:
        lian.execute(
            "INSERT INTO products (sku, mingcheng, leibie, kucun, danjia, danwei) "
            "VALUES ('CESHI2','并发测试品2','测试',10,1.0,'个')"
        )

    jieguo = []
    suo = threading.Lock()

    def _tou():
        try:
            zt, _ = kucun.yuliuku_cun(ku, "BF-SAME", "CESHI2", 4)
            with suo:
                jieguo.append(zt)
        except kucun.KucunCuowu as e:
            with suo:
                jieguo.append("cuowu%d" % e.zhuangtai_ma)

    xs = [threading.Thread(target=_tou) for _ in range(2)]
    for x in xs: x.start()
    for x in xs: x.join()

    assert kucun.chaxun_dan_ge(ku, "CESHI2")["kucun"] == 6, "只应扣一次 4"
    assert len(kucun.chaxun_yuliu(ku, request_id="BF-SAME")) == 1


# ==================== 自主功能：规则版本 ====================

def test_guize_danci_shangxian(ku):
    kucun.baocun_guize(ku, "v-test", meilei_zuida=100, danci_zuida=3)
    tongguo, banben, shuo = kucun.jiancha_guize(ku, "BOOK", 4, "v-test")
    assert tongguo is False
    assert banben == "v-test"
    assert "单次" in shuo


def test_guize_leiji_shangxian(ku):
    """累计口径：同一 sku 已领的数量要算进去。"""
    kucun.baocun_guize(ku, "v-test2", meilei_zuida=5, danci_zuida=10)
    kucun.yuliuku_cun(ku, "G-001", "BOOK", 3, guize_banben="v-test2")

    tongguo, _, shuo = kucun.jiancha_guize(ku, "BOOK", 3, "v-test2")
    assert tongguo is False
    assert "累计" in shuo

    tongguo2, _, _ = kucun.jiancha_guize(ku, "BOOK", 2, "v-test2")
    assert tongguo2 is True


def test_guize_banben_beijilu_jin_yuliu(ku):
    """每笔记录要写清当时用的是哪一版规则，否则事后审计说不清。"""
    kucun.baocun_guize(ku, "v-g1", meilei_zuida=100, danci_zuida=5)
    kucun.yuliuku_cun(ku, "G-002", "BOOK", 2, guize_banben="v-g1")
    hang = kucun.chaxun_yuliu(ku, request_id="G-002")
    assert hang[0]["guize_banben"] == "v-g1"


def test_meiyou_guize_shibukan_buxian(ku):
    """没有规则版本时要明确说"未做校验"，不能假装有规则。"""
    tongguo, banben, shuo = kucun.jiancha_guize(ku, "BOOK", 1, "buzhidaode")
    assert tongguo is True
    assert banben == "无规则"
    assert "未做" in shuo


# ==================== 持久化 ====================

def test_zhongzi_chongfu_zhixing_bu_huanyuan_kucun(ku):
    """
    种子脚本必须幂等，而且**不能把已经扣掉的库存还原**。
    否则反复跑种子脚本会把测试证据冲掉。
    """
    from zhongzi import SHANGPIN_LIEBIAO
    kucun.yuliuku_cun(ku, "P-001", "A4ZHI", 20)
    assert kucun.chaxun_dan_ge(ku, "A4ZHI")["kucun"] == 100

    kucun.chushihua_zhongzi(ku, SHANGPIN_LIEBIAO)      # 再灌一次
    assert kucun.chaxun_dan_ge(ku, "A4ZHI")["kucun"] == 100, "种子把库存还原了！"


def test_shuju_ku_zhongqi_hou_jilu_hai_zai(ku):
    """模拟重启：关掉连接再重新打开，记录和库存都还在（SQLite 文件持久化）。"""
    kucun.yuliuku_cun(ku, "P-002", "BOOK", 7)
    # 重新打开连接（函数内部本来就是每次新开，这里相当于"新进程"）
    assert kucun.chaxun_dan_ge(ku, "BOOK")["kucun"] == 53
    hang = kucun.chaxun_yuliu(ku, request_id="P-002")
    assert len(hang) == 1 and hang[0]["quantity"] == 7
