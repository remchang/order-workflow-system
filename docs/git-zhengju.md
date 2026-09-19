# 个人开发过程与 Git 证据对照表（实验06）

仓库：https://github.com/remchang/order-workflow-system

---

## 一、Issue 与 Commit 对照

| Issue | 标题 | 阶段 | 关联 Commit |
| --- | --- | --- | --- |
| #1 | 服务契约与数据归属设计 | 基线 | `chore(baseline)` |
| #2 | Node-RED 基线流程与固定版本 | 基线 | `chore(baseline)` / `feat(flows)` |
| #3 | 独立库存服务与事务 | 核心功能 | `feat(service)` |
| #4 | 编排主链路与错误分类 | 核心功能 | `feat(flows)` |
| #5 | 用户操作页面 | 核心功能 | `feat(web)` |
| #6 | 幂等与异常策略 | 核心功能 | `feat(service)` / `feat(flows)` |
| #7 | 自主扩展：领用上限规则与规则版本 | 自主功能 | `feat(guize)` |
| #8 | 测试、复现与交付文档 | 测试 / 文档 | `test(tests)` / `docs` |

Issue 正文留档在 `docs/issue.md`。

## 二、Commit 一览

| # | 类型 | 覆盖阶段 | 主要内容 |
| --- | --- | --- | --- |
| 1 | `chore(baseline)` | 基线 | 依赖锁文件、settings.js、LICENSE、NOTICE、基线流程 |
| 2 | `feat(service)` | 核心功能 | `kucun.py` 事务与幂等、`app.py` 契约、种子数据 |
| 3 | `feat(flows)` | 核心功能 | `orders.json` 编排、校验分支、错误分类、Catch |
| 4 | `feat(web)` | 核心功能 | 操作页面（表单/列表/筛选/详情） |
| 5 | `feat(guize)` | 自主功能 | 领用上限规则 + 规则版本记录 |
| 6 | `test(tests)` | 测试 | 61 条 pytest（契约 / 编排静态验证 / 库存幂等） |
| 7 | `feat(scripts)` | 交付 | 安装/启动/停止/种子/演示/测试脚本 |
| 8 | `docs` | 文档 | README、实验报告、测试记录、Issue、演示素材 |

覆盖实验要求的五类：**基线 / 核心功能 / 自主功能 / 测试 / 文档**。

## 三、分支与 PR

- 特性分支：`feature/order-workflow`
- PR 关联 Issue #4 #5 #6，描述里附了 pytest 输出和演示用例结果
- 合并前完成一次有文字记录的自我 Code Review（见下节）

```powershell
git log --oneline --graph --decorate --all -n 30
git shortlog -sne HEAD
```

## 四、自我 Code Review 检查清单

| # | 检查项 | 结论 |
| --- | --- | --- |
| 1 | Node-RED 有没有直接读写 kucun.db？ | ✅ 没有。有静态测试扫 Function 代码和 URL |
| 2 | 库存扣减是"先查再扣"还是"条件更新"？ | ✅ 条件更新 `WHERE kucun >= ?` + 检查 rowcount |
| 3 | rowcount 为 0 时返回成功了吗？ | ✅ 没有，回滚并返回 409 |
| 4 | 幂等只绑了编号还是也绑了内容？ | ✅ 都绑了。同号不同内容返回 409，避免假成功 |
| 5 | 超时被当成失败了吗？ | ✅ 没有。文案引导"先查编号再重试"，有测试盯文案 |
| 6 | 5xx 和业务拒绝分开了吗？ | ✅ 分开。409 业务拒绝 / 502 依赖失败 |
| 7 | Function 有没有丢 msg.req / msg.res？ | ✅ 没有。有静态测试禁止 `return {` 新对象 |
| 8 | 每个入口都能走到 HTTP Response 吗？ | ✅ 有可达性遍历测试 |
| 9 | 规则校验在扣减之前还是之后？ | ✅ 之前。有测试断言被拒请求不改库存 |
| 10 | 每笔记录带规则版本吗？ | ✅ 带 `guize_banben` |
| 11 | 页面会不会自己算库存？ | ✅ 不会，只显示服务端返回值 |
| 12 | 前端有没有拼 innerHTML 传不可信文本？ | ✅ 全部过 `zhuanYi()` |
| 13 | 有没有把用户输入交给 eval / 系统命令？ | ✅ 没有，全仓库搜不到 |
| 14 | 种子脚本会不会还原库存冲掉证据？ | ✅ 不会，用 INSERT OR IGNORE，有测试 |
| 15 | 编辑器绑回环了吗？ | ✅ `uiHost: "127.0.0.1"`，并注明开放前必须加认证 |
| 16 | 有没有把上游节点写成本人成果？ | ✅ 没有，NOTICE.md 里有逐项对照表 |
| 17 | 未实跑的部分有没有说清楚？ | ✅ README 与测试记录都标了"Node-RED 未实跑" |

## 五、踩过的坑

1. **规则版本排序失效**（最严重）。
   生效时间戳只精确到秒，同秒内两版排序不确定，
   刚存的新规则没生效，被拒的请求照样扣了库存。
   被 `test_guize_jujue_bu_dong_kucun` 抓到（`assert 51 == 60`）。

2. **.gitignore 的 `data/` + `!data/README.md` 不生效**。
   Git 不会进入被忽略的目录，"!" 例外也就无从谈起。
   正确写法是 `data/*` 再 `!data/README.md`。

3. **种子脚本差点写成会还原库存**。
   第一版用 `INSERT OR REPLACE`，反复跑会把测试扣掉的库存还原。
   改成 `INSERT OR IGNORE` 并补了测试。

4. **并发测试耗时**。
   最初把 `busy_timeout` 设成 1 秒，并发用例偶发失败；
   调到 5 秒后稳定。**宁可慢也不要 flaky**——
   会偶尔失败的测试很快就会被所有人忽略。

5. **FastAPI 的 422 早于业务校验**。
   收到 JSON 数组时框架层直接 422，我们自己的中文提示走不到。
   这不是 bug，是框架行为，测试期望要跟着调整。
