# -*- coding: utf-8 -*-
"""
kucun.py —— 库存数据访问层（SQLite）。

本模块是整个实验里"数据所有权"的落点：
    · products / reservations 两张表只由本模块访问；
    · Node-RED 只能通过 HTTP 调用，**不允许**直接读这个库文件；
    · 幂等、库存扣减、冲突识别必须放在同一个事务里。

为什么不用 Node-RED 的文件 Context 存库存：
    Context 有缓存和定期刷盘行为，不是事务，进程崩了可能丢写；
    也没有唯一约束，没法保证同一 request_id 只扣一次。
    重要业务数据必须落到关系库，事务成功后再返回。
"""
import datetime
import os
import sqlite3
import threading
from contextlib import contextmanager

# 数据库路径。放在项目的 data/ 下，不进 Git（见 .gitignore）。
MOREN_KU_LUJING = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "kucun.db"
)

# SQLite 写锁等待时间（毫秒）。并发测试时会用到——
# 不设等待的话，第二个写请求直接抛 database is locked。
DENGDAI_Haomiao = 5000

# 单进程内的写锁。SQLite 自己的锁在 Windows 上行为不够稳，
# 加一层应用级锁让"临界库存"测试可预测。
_XIE_SUO = threading.Lock()


class KucunCuowu(Exception):
    """业务错误。带上 HTTP 状态码，让上层直接映射。"""

    def __init__(self, zhuangtai_ma, xiaoxi, **qita):
        super().__init__(xiaoxi)
        self.zhuangtai_ma = zhuangtai_ma
        self.xiaoxi = xiaoxi
        self.qita = qita


def _xianzai_iso():
    """
    当前时间，**精确到微秒**。

    为什么不用 time.strftime("%Y-%m-%dT%H:%M:%S")：
        秒级精度下，同一个秒内建的两个规则版本时间戳完全相同，
        "ORDER BY 生效时间 DESC 取最新" 就会退化成任意顺序——
        测试里真实踩到了这个坑：刚存的 v4 没生效，用的还是启动时的 v1，
        被规则拒绝的请求照样扣了库存。
    微秒级 + ISO 格式，字符串排序就等于时间排序，问题消失。
    """
    return datetime.datetime.now().isoformat(timespec="microseconds")


@contextmanager
def _lianjie(ku_lujing=MOREN_KU_LUJING):
    """打开连接，开 WAL 与外键，用完关掉。"""
    os.makedirs(os.path.dirname(ku_lujing), exist_ok=True)
    lian = sqlite3.connect(ku_lujing, timeout=DENGDAI_Haomiao / 1000.0,
                           isolation_level=None)   # 自己管事务
    lian.row_factory = sqlite3.Row
    try:
        lian.execute("PRAGMA journal_mode=WAL")
        lian.execute("PRAGMA foreign_keys=ON")
        lian.execute("PRAGMA busy_timeout=%d" % DENGDAI_Haomiao)
        yield lian
    finally:
        lian.close()


def chuangjian_biao(ku_lujing=MOREN_KU_LUJING):
    """建表。幂等，可以反复调用。"""
    with _lianjie(ku_lujing) as lian:
        lian.execute("""
            CREATE TABLE IF NOT EXISTS products (
                sku         TEXT PRIMARY KEY,
                mingcheng   TEXT NOT NULL,
                leibie      TEXT NOT NULL,
                kucun       INTEGER NOT NULL CHECK (kucun >= 0),
                danjia      REAL NOT NULL DEFAULT 0,
                danwei      TEXT NOT NULL DEFAULT '件'
            )
        """)
        lian.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                request_id  TEXT PRIMARY KEY,
                sku         TEXT NOT NULL,
                quantity    INTEGER NOT NULL CHECK (quantity > 0),
                shengyu     INTEGER NOT NULL,
                zhuangtai   TEXT NOT NULL,
                neirong_zhiwen TEXT NOT NULL,
                guize_banben TEXT NOT NULL,
                chuangjian_shijian TEXT NOT NULL,
                FOREIGN KEY (sku) REFERENCES products(sku)
            )
        """)
        lian.execute("""
            CREATE TABLE IF NOT EXISTS guize_banben (
                banben      TEXT PRIMARY KEY,
                meilei_zuida INTEGER NOT NULL,
                danci_zuida INTEGER NOT NULL,
                shengxiao_shijian TEXT NOT NULL
            )
        """)
        lian.execute("CREATE INDEX IF NOT EXISTS idx_res_sku ON reservations(sku)")
        lian.execute("CREATE INDEX IF NOT EXISTS idx_res_zhuangtai ON reservations(zhuangtai)")


def _neirong_zhiwen(sku, quantity):
    """
    请求内容的稳定指纹。

    实验思考题问："唯一请求编号为何还要与请求内容绑定？"
    答：因为没有这个，"同号不同内容"就会被静默当成重复请求返回成功，
    调用方以为自己的新请求被处理了，其实数据完全没动。
    这里用 sku + quantity 的规范化字符串，不引入随机量，保证同内容同指纹。
    """
    return "%s|%d" % (str(sku).strip().upper(), int(quantity))


def chaxun_shangpin(ku_lujing=MOREN_KU_LUJING):
    """列出全部商品。"""
    with _lianjie(ku_lujing) as lian:
        hang = lian.execute(
            "SELECT sku, mingcheng, leibie, kucun, danjia, danwei "
            "FROM products ORDER BY sku"
        ).fetchall()
    return [dict(h) for h in hang]


def chaxun_dan_ge(ku_lujing, sku):
    with _lianjie(ku_lujing) as lian:
        hang = lian.execute(
            "SELECT sku, mingcheng, leibie, kucun, danjia, danwei "
            "FROM products WHERE sku = ?", (sku,)
        ).fetchone()
    return dict(hang) if hang else None


def yuliuku_cun(ku_lujing, request_id, sku, quantity, guize_banben="v1"):
    """
    预留库存。★ 本模块最核心的函数。

    整个流程在一个事务里完成：
        ① 查这个 request_id 有没有已经处理过
           - 有且内容相同 → 幂等命中，直接返回原结果，**不重复扣减**
           - 有但内容不同 → 抛 409 冲突
        ② 查商品存不存在
        ③ 查库存够不够（不够抛 409）
        ④ 条件更新库存（WHERE kucun >= ?），受影响行数为 0 就回滚
        ⑤ 写 reservations

    为什么④要用"条件更新 + 检查受影响行数"：
        如果先 SELECT 再 UPDATE，两条并发请求可能都读到"库存够"，
        然后都去扣，就超卖了。把条件写进 WHERE 让数据库自己做原子判断，
        受影响行数为 0 就说明被别人抢先了，必须回滚。
        **受影响行数为 0 时绝对不能仍然返回成功。**

    返回 (zhuangtai, shuju)：
        "xinjian"  → 新建成功
        "chongfu"  → 幂等命中，返回已有结果
    """
    rid = str(request_id).strip()
    sku_gui = str(sku).strip().upper()
    qty = int(quantity)

    if not rid:
        raise KucunCuowu(400, "request_id 不能为空")
    if qty <= 0:
        raise KucunCuowu(400, "quantity 必须大于 0")

    zhiwen = _neirong_zhiwen(sku_gui, qty)
    shijian = _xianzai_iso()

    with _XIE_SUO:
        with _lianjie(ku_lujing) as lian:
            lian.execute("BEGIN IMMEDIATE")
            try:
                # ① 幂等检查
                jiu = lian.execute(
                    "SELECT request_id, sku, quantity, shengyu, zhuangtai, neirong_zhiwen "
                    "FROM reservations WHERE request_id = ?", (rid,)
                ).fetchone()

                if jiu is not None:
                    if jiu["neirong_zhiwen"] != zhiwen:
                        lian.execute("ROLLBACK")
                        raise KucunCuowu(
                            409,
                            "请求编号 %s 已存在，但内容不同"
                            "（原：%s×%d，现：%s×%d）"
                            % (rid, jiu["sku"], jiu["quantity"], sku_gui, qty),
                            lei_xing="neirong_chongtu",
                        )
                    lian.execute("COMMIT")
                    return "chongfu", {
                        "request_id": rid,
                        "sku": jiu["sku"],
                        "quantity": jiu["quantity"],
                        "shengyu": jiu["shengyu"],
                        "zhuangtai": jiu["zhuangtai"],
                        "chongfu": True,
                    }

                # ② 商品存在性
                sp = lian.execute(
                    "SELECT sku, mingcheng, kucun, danwei FROM products WHERE sku = ?",
                    (sku_gui,)
                ).fetchone()
                if sp is None:
                    lian.execute("ROLLBACK")
                    raise KucunCuowu(404, "商品 %s 不存在" % sku_gui,
                                     lei_xing="shangpin_bucunzai")

                # ③ 库存够不够（先给一个友好错误，真正的把关在④）
                if sp["kucun"] < qty:
                    lian.execute("ROLLBACK")
                    raise KucunCuowu(
                        409,
                        "库存不足：%s 现有 %d，申请 %d"
                        % (sku_gui, sp["kucun"], qty),
                        lei_xing="kucun_buzu",
                        kucun_xianyou=sp["kucun"],
                        shenqing=qty,
                    )

                # ④ 条件更新 —— 原子扣减
                you = lian.execute(
                    "UPDATE products SET kucun = kucun - ? "
                    "WHERE sku = ? AND kucun >= ?",
                    (qty, sku_gui, qty)
                )
                if you.rowcount != 1:
                    # 走到这里说明并发里被别人抢先了，绝不能返回成功
                    lian.execute("ROLLBACK")
                    raise KucunCuowu(
                        409,
                        "库存刚刚被其他请求占用，请重试",
                        lei_xing="kucun_buzu",
                    )

                shengyu = int(sp["kucun"]) - qty

                # ⑤ 写预留记录。主键冲突说明并发插入了同一个编号，回滚。
                try:
                    lian.execute(
                        "INSERT INTO reservations "
                        "(request_id, sku, quantity, shengyu, zhuangtai, "
                        " neirong_zhiwen, guize_banben, chuangjian_shijian) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (rid, sku_gui, qty, shengyu, "已完成", zhiwen,
                         guize_banben, shijian)
                    )
                except sqlite3.IntegrityError:
                    lian.execute("ROLLBACK")
                    raise KucunCuowu(409, "请求编号 %s 已被并发占用" % rid,
                                     lei_xing="neirong_chongtu")

                lian.execute("COMMIT")
                return "xinjian", {
                    "request_id": rid,
                    "sku": sku_gui,
                    "quantity": qty,
                    "shengyu": shengyu,
                    "zhuangtai": "已完成",
                    "chongfu": False,
                    "guize_banben": guize_banben,
                }
            except KucunCuowu:
                raise
            except Exception:
                try:
                    lian.execute("ROLLBACK")
                except Exception:      # noqa: BLE001
                    pass
                raise


def chaxun_yuliu(ku_lujing, request_id=None, zhuangtai=None, zuiduo=200):
    """查预留记录。给列表和详情接口用。"""
    sql = ("SELECT request_id, sku, quantity, shengyu, zhuangtai, "
           "guize_banben, chuangjian_shijian FROM reservations WHERE 1=1")
    canshu = []
    if request_id:
        sql += " AND request_id = ?"
        canshu.append(request_id)
    if zhuangtai:
        sql += " AND zhuangtai = ?"
        canshu.append(zhuangtai)
    sql += " ORDER BY chuangjian_shijian DESC, request_id DESC LIMIT ?"
    canshu.append(int(zuiduo))

    with _lianjie(ku_lujing) as lian:
        hang = lian.execute(sql, canshu).fetchall()
    return [dict(h) for h in hang]


# ---------------- 自主功能：领用上限规则（带版本） ----------------

def baocun_guize(ku_lujing, banben, meilei_zuida, danci_zuida):
    """保存一个规则版本。同一版本号重复保存会覆盖（方便反复实验）。"""
    with _lianjie(ku_lujing) as lian:
        lian.execute(
            "INSERT OR REPLACE INTO guize_banben "
            "(banben, meilei_zuida, danci_zuida, shengxiao_shijian) VALUES (?,?,?,?)",
            (banben, int(meilei_zuida), int(danci_zuida), _xianzai_iso())
        )
    return chaxun_guize(ku_lujing, banben)


def chaxun_guize(ku_lujing, banben=None):
    """查规则。不传版本就取最新生效的那个。"""
    with _lianjie(ku_lujing) as lian:
        if banben:
            hang = lian.execute(
                "SELECT banben, meilei_zuida, danci_zuida, shengxiao_shijian "
                "FROM guize_banben WHERE banben = ?", (banben,)
            ).fetchone()
        else:
            hang = lian.execute(
                "SELECT banben, meilei_zuida, danci_zuida, shengxiao_shijian "
                "FROM guize_banben ORDER BY shengxiao_shijian DESC LIMIT 1"
            ).fetchone()
    return dict(hang) if hang else None


def jiancha_guize(ku_lujing, sku, quantity, banben=None):
    """
    按规则校验本次申请。返回 (是否通过, 规则版本, 说明)。

    规则（自主功能，上游没有）：
      · 单次领用数量不能超过 danci_zuida;
      · 同一个商品在**同一规则版本有效期内**的累计领用不能超过 meilei_zuida。
        累计口径是"该 sku 已成功预留的数量之和"。

    为什么要记录规则版本：规则改过之后，历史记录必须还能说清
    "当时是按哪一版规则通过的"。没有版本号，事后审计就是一锅粥。
    """
    gz = chaxun_guize(ku_lujing, banben)
    if gz is None:
        # 没有规则就当不限制，但要把这一点明确返回，不能装作有规则
        return True, "无规则", "当前没有任何规则版本，未做上限校验"

    if quantity > gz["danci_zuida"]:
        return False, gz["banben"], (
            "单次领用超过上限：本规则版本单次最多 %d，本次申请 %d"
            % (gz["danci_zuida"], quantity)
        )

    with _lianjie(ku_lujing) as lian:
        yi = lian.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS he FROM reservations "
            "WHERE sku = ? AND zhuangtai = '已完成'", (str(sku).strip().upper(),)
        ).fetchone()["he"]

    if int(yi) + quantity > gz["meilei_zuida"]:
        return False, gz["banben"], (
            "累计领用超过上限：本规则版本对 %s 累计最多 %d，"
            "已领 %d，本次再领 %d 就超了"
            % (sku, gz["meilei_zuida"], int(yi), quantity)
        )

    return True, gz["banben"], "规则校验通过"


def chushihua_zhongzi(ku_lujing, shangpin_liebiao):
    """
    写入种子数据。幂等：已存在的 sku 不会被覆盖库存
    （否则反复跑种子脚本会把测试中扣掉的库存还原，破坏证据）。
    """
    chuangjian_biao(ku_lujing)
    with _lianjie(ku_lujing) as lian:
        for sp in shangpin_liebiao:
            lian.execute(
                "INSERT OR IGNORE INTO products "
                "(sku, mingcheng, leibie, kucun, danjia, danwei) VALUES (?,?,?,?,?,?)",
                (sp["sku"], sp["mingcheng"], sp["leibie"], sp["kucun"],
                 sp["danjia"], sp["danwei"])
            )
    return chaxun_shangpin(ku_lujing)
