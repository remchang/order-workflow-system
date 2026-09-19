# 测试记录（实验06）

> 环境：Windows，Node 22.22.2，Python 3.13.14，SQLite（标准库）。
> 所有命令在项目根目录执行。

---

## 一、自动化测试（实测 ✅ 61 条）

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:warnings
```

**实际输出：**

```
.............................................................            [100%]
61 passed in 45.63s
```

### 分布

| 文件 | 条数 | 覆盖 |
| --- | --- | --- |
| `tests/test_api.py` | 22 | 健康、商品、预留、幂等、冲突、缺货、参数校验、查询、规则 |
| `tests/test_kucun.py` | 20 | 事务、幂等、编号冲突、库存边界、并发、规则、持久化 |
| `tests/test_flows.py` | 14 | 流程 JSON 静态验证（连线、输出路数、msg.res、可达性、边界） |

### 对应实验要求的测试类型

| 类型 | 最低数量 | 本仓库 |
| --- | --- | --- |
| 服务与契约测试 | 6 | 22 |
| 编排功能测试 | 6 | 14 |
| 库存与幂等测试 | 5 | 20 |
| 故障与恢复测试 | 4 | 503 / 冲突 / 临界 / 重启持久化（含在上两块里） |
| 界面与自主测试 | 5 | 规则边界 5 条 + 页面调真实接口的静态检查 |

### 运行耗时说明

45 秒里绝大部分花在**并发测试**上：
`test_bingfa_bu_chaomai` 和 `test_bingfa_tongyibianhao_zhi_kou_yici`
要用真实线程竞争 SQLite 的写锁，`busy_timeout` 设了 5 秒。
这是刻意的——把超时时间调小会让并发测试变得不稳定，
而"测试偶尔失败"比"测试慢"糟糕得多。

---

## 二、关键用例的实际断言

### 2.1 并发不超卖

```python
# 建一个库存为 3 的商品，两个线程各申请 2
assert sorted(jieguo) == ["失败409", "成功"]
assert kucun.chaxun_dan_ge(ku, "CESHI")["kucun"] == 1
assert sheng >= 0, "库存出现负数，说明条件更新没起作用"
```

**结果：通过。** 恰好一条成功，库存从 3 变 1（不是 -1）。

### 2.2 幂等

```python
kucun.yuliuku_cun(ku, "T-002", "BOOK", 3)
zhuangtai, jieguo = kucun.yuliuku_cun(ku, "T-002", "BOOK", 3)
assert zhuangtai == "chongfu"
assert kucun.chaxun_dan_ge(ku, "BOOK")["kucun"] == 57   # 60-3，只扣一次
assert len(kucun.chaxun_yuliu(ku, request_id="T-002")) == 1
```

**结果：通过。**

### 2.3 编号内容冲突

```python
kucun.yuliuku_cun(ku, "T-003", "BOOK", 3)
# 同编号、数量改成 4
assert e.value.zhuangtai_ma == 409
assert kucun.chaxun_dan_ge(ku, "BOOK")["kucun"] == 57   # 冲突请求没改库存
```

**结果：通过。**

### 2.4 种子幂等（不能还原库存）

```python
kucun.yuliuku_cun(ku, "P-001", "A4ZHI", 20)   # 120 -> 100
kucun.chushihua_zhongzi(ku, SHANGPIN_LIEBIAO)  # 再灌一次种子
assert kucun.chaxun_dan_ge(ku, "A4ZHI")["kucun"] == 100   # 不能变回 120
```

**结果：通过。** 这条很重要——如果种子脚本会把库存还原，
反复跑演示脚本就会把证据冲掉。

---

## 三、失败用例与修复记录

### 失败 1：规则版本没生效，被拒的请求改了库存

**现象**

```
tests\test_api.py:182: in test_guize_jujue_bu_dong_kucun
    assert hou_ku == qian_ku, "被规则拒绝的请求改了库存！"
E   assert 51 == 60
```

**根因**

规则生效时间戳用的是 `time.strftime("%Y-%m-%dT%H:%M:%S")`，**只到秒**。
测试里：

1. 应用启动 → 建规则 `v1`（单次上限 20）
2. 测试立刻建规则 `v4`（单次上限 2）
3. 两次调用在**同一个秒内**

`ORDER BY shengxiao_shijian DESC LIMIT 1` 遇到完全相同的时间戳时，
顺序是未定义的。实际取到了 `v1`，于是单次上限是 20，
申请 9 件"合法"，库存被扣了 9（60 → 51）。

**为什么手测发现不了**

人手点两下至少隔几秒，永远不会撞上。只有自动化测试
在同一秒内连续建两个版本才会暴露。

**修复**

```python
def _xianzai_iso():
    """精确到微秒。秒级精度下同秒内两版排序不确定——测试抓到过这个坑。"""
    return datetime.datetime.now().isoformat(timespec="microseconds")
```

ISO 格式的字符串排序 = 时间排序，问题消失。

**回归**：修复后 61 条全过。

### 失败 2：非对象请求体返回 422 而不是 400

**现象**

```
assert 422 == 400
```

**根因**

`POST /reserve` 的参数声明是 `ti: dict`。
FastAPI 在框架层就会把 JSON 数组判为类型不符，直接返回 422，
我们自己的中文校验代码根本走不到。

**判定：这不是 bug，是测试期望写得过严。**

指导书对这个口径写的原文是"参数错误返回 400 或明确记录的 422"，
所以 422 是允许的。改测试接受两者，并在测试里写明原因。

**修复**：`assert x.status_code in (400, 422)`，并加注释说明。

---

## 四、依赖版本与文档建议的差异（如实记录）

| 包 | 文档建议 | 实际装到 | 原因 |
| --- | --- | --- | --- |
| fastapi | 0.115.12 | **0.141.1** | Python 3.13 环境下旧版无可用组合 |
| uvicorn | 0.34.3 | **0.53.0** | 同上 |
| starlette | — | 1.6.0 | — |
| pydantic | — | 2.13.5 | — |
| httpx | — | 0.28.1 | — |
| pytest | — | 9.1.1 | — |

代码没有依赖任何被移除的 API，61 条测试全过。
`service/requirements.txt` 按 `pip freeze` 的**实际结果**写，不写推测版本。

### 安装方式

直连 PyPI 实测约 100 KB/s 且频繁超时，最终用阿里云镜像完成：

```powershell
.\.venv\Scripts\python -m pip install -r service\requirements.txt `
  -i https://mirrors.aliyun.com/pypi/simple/ `
  --trusted-host mirrors.aliyun.com
```

`scripts/anzhuang.ps1` 已把这个镜像作为默认值。

---

## 五、★ 未实跑的部分（重要，如实记录）

### 5.1 Node-RED 没有在本机跑起来

**原因**：`npm install node-red@5.0.7` 需要下载约 80MB 依赖，
本机网络实测约 100 KB/s 且会中断，时间成本过高。

**因此下面这些没有实测证据**：

- `node node_modules/node-red/red.js ... flows/orders.json` 能成功 Deploy
- `http://127.0.0.1:1880/health` 返回 `{"status":"ok"}`
- `http://127.0.0.1:1880/orders.html` 页面能打开
- `scripts/yanshi.ps1` 的 7 条端到端用例

**已经做了的替代验证**：

1. 流程 JSON 的**静态验证**：14 条测试检查连线目标是否存在、
   Function 输出路数是否与接线组数一致、入口能否走到响应节点、
   是否保留了 `msg.req/msg.res`、Catch 后面是否接了响应。
2. `scripts/ceshi.ps1` 的第 ③ 步用 Node **真实解析**两个流程 JSON，
   确认语法合法并统计节点类型。
3. `settings.js` 用 Node `require()` 真实加载，确认导出的配置项齐全。

**这些不能替代端到端运行**，在 README 和实验报告里都标明了。

### 5.2 库存服务是实跑的

上面这些未跑的部分**不涉及库存服务**。库存服务本身：

- 61 条测试全部实跑通过（含真实并发线程竞争）
- SQLite 事务、幂等、条件更新、规则版本都是真实执行的代码路径
- 持久化测试用真实文件数据库验证

---

## 六、测试证据清单

| 要求的证据 | 在哪 |
| --- | --- |
| 契约、幂等与库存边界的自动化测试 | `tests/` 61 条，`pytest -q` 输出见第一节 |
| 并发边界证据 | `test_bingfa_bu_chaomai` 断言"恰好一条成功 + 库存为 1 而非 -1" |
| 故障与恢复证据 | 503 分支、409 冲突、临界库存、重启持久化各自有用例 |
| 演示数据 | `service/zhongzi.py` 11 种商品（充足/低库存/零库存三种状态） |
| 运行命令与断言 | `scripts/ceshi.ps1` 分四步可重复执行 |
| 未实跑部分的边界 | 本节第 5 节 + README「已知限制」 |

---

## 七、复现步骤

```powershell
git clone https://github.com/remchang/order-workflow-system
cd order-workflow-system
.\scripts\anzhuang.ps1     # 建 venv + 装依赖 + 装 Node-RED + 跑测试
.\scripts\qidong.ps1       # 起两个进程
.\scripts\yanshi.ps1       # 跑 7 条演示用例
.\scripts\tingzhi.ps1      # 停
```
