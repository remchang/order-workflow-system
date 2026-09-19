# data/ 说明

这个目录是**运行时目录**，内容不进 Git（见根目录 `.gitignore`）。

| 路径 | 是什么 | 重建方式 |
| --- | --- | --- |
| `data/kucun.db` | 库存服务的 SQLite 数据库（商品、预留记录、规则版本） | `.\scripts\zhongzhi.ps1` |
| `data/kucun.db-wal` | SQLite 的 WAL 日志（预写日志） | 自动生成 |
| `data/kucun.db-shm` | SQLite 的共享内存文件 | 自动生成 |
| `data/node-red/` | Node-RED 的 userDir（流程备份、`.config.*.json`、文件 Context 的落盘文件） | 启动 Node-RED 时自动生成 |

## 为什么不入库

`kucun.db` 里存的是**运行态**：演示过程中扣掉的库存、产生的预留记录。
它不属于源码，而且每次演示都不一样。

入库的话会造成两个问题：

1. 别人克隆下来看到的是"库存已经被扣过"的状态，不是干净的初始状态。
2. Git 会把每次演示的数据库都存一份历史，仓库迅速膨胀。

所以入库的是**种子数据**（`service/zhongzi.py` 里的 11 种商品），
数据库本身用脚本生成。

## 重建

```powershell
# 幂等：已存在的商品不覆盖库存（故意的，见下面说明）
.\scripts\zhongzhi.ps1

# 破坏性：删库重建，要手打确认
.\scripts\zhongzhi.ps1 -Chongjian
```

**为什么默认的种子脚本是幂等的、且不还原库存**：
如果每次跑种子都把所有库存还原成初始值，
那演示过程中产生的"扣减证据"就被冲掉了，
事后无法验证"库存确实被扣过"。所以用 `INSERT OR IGNORE`。

## 备份

直接复制 `data\kucun.db` 就行（最好先停服务）：

```powershell
.\scripts\tingzhi.ps1
Copy-Item data\kucun.db data\kucun.db.bak
```

恢复同理，复制回去再启动。

> SQLite 用 WAL 模式，热备份时最好一起复制 `-wal` 和 `-shm` 文件，
> 或者先停服务让 WAL 合并回主库。
