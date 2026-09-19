# 第三方资源与许可证说明（NOTICE）

本仓库是《开源软件与新技术》课程实验06 的**二次开发成品**。
下面逐项列出用到的上游项目、来源、版本和许可证。

---

## 一、运行时依赖

| 项目 | 用途 | 固定版本 | 许可证 | 来源 |
| --- | --- | --- | --- | --- |
| [node-red/node-red](https://github.com/node-red/node-red) | HTTP 编排、消息处理、错误捕获 | **5.0.7** | Apache-2.0 | npm `node-red@5.0.7` |
| [fastapi/fastapi](https://github.com/fastapi/fastapi) | 库存服务 Web 框架 | 见 `service/requirements.txt` | MIT | PyPI |
| [encode/uvicorn](https://github.com/encode/uvicorn) | ASGI 服务器 | 见 `service/requirements.txt` | BSD-3-Clause | PyPI |
| [pydantic/pydantic](https://github.com/pydantic/pydantic) | 请求体校验（FastAPI 依赖） | 见 `service/requirements.txt` | MIT | PyPI |
| [encode/httpx](https://github.com/encode/httpx) | 测试用 HTTP 客户端 | 见 `service/requirements.txt` | BSD-3-Clause | PyPI |
| [pytest-dev/pytest](https://github.com/pytest-dev/pytest) | 测试框架 | 见 `service/requirements.txt` | MIT | PyPI |
| Node.js | Node-RED 运行时 | 22.22.2 | MIT | 系统已安装 |
| SQLite | 库存与预留记录存储 | Python 自带 `sqlite3` | Public Domain | 标准库 |

## 二、我用到的上游能力 vs 自己实现的部分

**明确区分**（指导书要求"不能把上游已有节点写成本人开发成果"）：

| 能力 | 谁提供的 |
| --- | --- |
| 编辑和部署流程、HTTP In/Response、Switch、Function、HTTP Request、Catch 节点 | **上游 Node-RED** |
| ASGI 框架、路由、依赖注入、OpenAPI 文档页 | **上游 FastAPI** |
| 商品与库存模型、预留事务、幂等唯一约束、冲突识别 | **本人实现**（`service/kucun.py`） |
| 业务接口与状态码契约（400/404/409/422/503） | **本人设计**（`service/app.py`） |
| 领用上限规则 + 规则版本记录（自主功能） | **本人实现**（`service/kucun.py`、`service/app.py`） |
| 编排主链路、错误分类、超时引导 | **本人编写流程**（`flows/orders.json`） |
| 操作页面（表单/列表/详情/筛选） | **本人实现**（`web/`） |
| 测试用例（55 条） | **本人编写**（`tests/`） |

## 三、没有引入的东西

- **没有**使用 Node-RED 的旧版 Dashboard 插件（`node-red-dashboard`）。
  它已停止维护，且指导书明确不建议依赖。
- **没有**引入任何第三方 npm 节点。`settings.js` 里设了
  `functionExternalModules: false`，只用核心节点，保证流程在别人机器上
  导入就能跑，不需要额外装包。
- **没有**使用任何真实业务数据、真实支付、短信或生产系统接口。
  所有商品和库存都是虚构的种子数据。

## 四、数据来源

`service/zhongzi.py` 里的 11 种商品和库存数量是**本人虚构的演示数据**，
不含任何真实商品目录、价格或企业信息。可自由使用。

## 五、本仓库自己的许可证

**MIT**，见 [LICENSE](LICENSE)。与上游 Node-RED（Apache-2.0）、
FastAPI（MIT）、Uvicorn（BSD-3-Clause）均兼容。

## 六、关于 Node-RED 的 Apache-2.0 义务

Apache-2.0 要求保留版权与许可声明。本实验室**通过 npm 依赖**使用 Node-RED，
**没有修改也没有重新分发**它的源码，因此只需在本文件保留来源声明即可。

如果以后要修改 Node-RED 源码再分发，必须：

1. 保留原始版权声明和许可证全文；
2. 明确标注被修改过的文件；
3. 附带一份 Apache-2.0 许可证副本。
