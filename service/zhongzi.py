# -*- coding: utf-8 -*-
"""
zhongzi.py —— 演示用商品与库存种子数据。

实验要求"准备至少 10 种商品，包含充足、低库存和零库存数据"。
所以这里的库存是**故意做成阶梯**的，方便演示三种分支：

    充足  —— 正常提交，应该成功
    临界  —— 刚好够 / 差一点，用来测边界
    零库存 —— 必然走缺货分支（409）

所有商品都是虚构的，不接任何真实业务系统。
"""
import os

# 种子数据。sku 故意用大写，和 kucun.py 里的规范化（strip().upper()）保持一致。
SHANGPIN_LIEBIAO = [
    # ---------- 充足 ----------
    {"sku": "A4ZHI",   "mingcheng": "A4 打印纸（500 张/包）", "leibie": "办公耗材", "kucun": 120, "danjia": 22.50,  "danwei": "包"},
    {"sku": "QIANBI",  "mingcheng": "中性笔（黑，0.5mm）",     "leibie": "办公耗材", "kucun": 300, "danjia": 2.80,   "danwei": "支"},
    {"sku": "BENZI",   "mingcheng": "无线装订笔记本 A5",       "leibie": "办公耗材", "kucun": 80,  "danjia": 9.90,   "danwei": "本"},
    {"sku": "BOOK",    "mingcheng": "实验指导手册（印刷版）",   "leibie": "教学资料", "kucun": 60,  "danjia": 35.00,  "danwei": "册"},
    {"sku": "USBX",    "mingcheng": "USB 扩展坞 4 口",         "leibie": "电子设备", "kucun": 45,  "danjia": 68.00,  "danwei": "个"},
    {"sku": "WANGLUO", "mingcheng": "网线 3 米（超五类）",     "leibie": "电子设备", "kucun": 200, "danjia": 12.00,  "danwei": "根"},

    # ---------- 低库存 / 临界 ----------
    {"sku": "SHUBIAO", "mingcheng": "无线鼠标",                "leibie": "电子设备", "kucun": 3,   "danjia": 89.00,  "danwei": "个"},
    {"sku": "JIANPAN", "mingcheng": "机械键盘（青轴）",        "leibie": "电子设备", "kucun": 1,   "danjia": 259.00, "danwei": "个"},
    {"sku": "YIDONGP", "mingcheng": "移动硬盘 1TB",            "leibie": "电子设备", "kucun": 5,   "danjia": 399.00, "danwei": "个"},

    # ---------- 零库存 ----------
    {"sku": "TOUYING", "mingcheng": "便携投影仪",              "leibie": "教学设备", "kucun": 0,   "danjia": 2199.0, "danwei": "台"},
    {"sku": "SANJIAO", "mingcheng": "三脚架（相机用）",        "leibie": "教学设备", "kucun": 0,   "danjia": 149.00, "danwei": "个"},
    {"sku": "HUABAN",  "mingcheng": "白板（1.2m×0.9m）",       "leibie": "教学设备", "kucun": 4,   "danjia": 320.00, "danwei": "块"},
]

# 类别清单，给规则用
LEIBIE_LIEBIAO = sorted({s["leibie"] for s in SHANGPIN_LIEBIAO})

# 预设的 6 条演示申请（正常 / 异常都有）
YANSHI_SHENQING = [
    {"request_id": "SY-001", "sku": "A4ZHI",   "quantity": 5,   "yuqi": "正常：充足库存"},
    {"request_id": "SY-002", "sku": "SHUBIAO", "quantity": 2,   "yuqi": "正常：低库存但够"},
    {"request_id": "SY-003", "sku": "TOUYING", "quantity": 1,   "yuqi": "异常：零库存 → 409"},
    {"request_id": "SY-004", "sku": "JIANPAN", "quantity": 5,   "yuqi": "异常：库存不足 → 409"},
    {"request_id": "SY-005", "sku": "A4ZHI",   "quantity": 0,   "yuqi": "异常：数量非法 → 400"},
    {"request_id": "SY-006", "sku": "BUCUNZAI","quantity": 1,   "yuqi": "异常：商品不存在 → 404"},
]


def baozheng_shuju_mulu(lu_jing):
    """确保数据库所在目录存在（SQLite 不会自己建目录）。"""
    mulu = os.path.dirname(lu_jing)
    if mulu and not os.path.exists(mulu):
        os.makedirs(mulu, exist_ok=True)
