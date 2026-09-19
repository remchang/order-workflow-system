/**
 * settings.js —— Node-RED 配置
 *
 * 三个要点：
 *   ① uiHost 绑 127.0.0.1：编辑器和 API 都不暴露到局域网。
 *      开放访问前必须先配认证，本实验不做这一步，所以只绑回环。
 *   ② httpStatic 指到 ./web：让操作页面和 API 同源，
 *      省掉跨域问题，也不用额外起一个前端服务器。
 *      页面路径就是 http://127.0.0.1:1880/orders.html
 *   ③ contextStorage 用 localfilesystem：
 *      默认的内存 Context 重启就没了。文件 Context 会落盘，
 *      **但它有缓存和定期刷盘行为，不是事务**，
 *      所以只能存"异常记录"这种参考信息，
 *      库存和预留记录必须写 SQLite（由独立库存服务负责）。
 */
const path = require("path");

module.exports = {
    uiHost: "127.0.0.1",
    uiPort: 1880,

    // 编辑器挪到 /editor，避免和 httpStatic 的页面路径打架
    httpAdminRoot: "/editor",
    httpNodeRoot: "/",

    // 操作页面用静态目录提供，和 API 同源
    httpStatic: path.join(__dirname, "web"),

    contextStorage: {
        default: { module: "localfilesystem" }
    },

    // 不需要自带的 projects（Git 集成），本实验的版本管理在仓库里做
    editorTheme: {
        projects: { enabled: false }
    },

    logging: {
        console: {
            level: "info",
            metrics: false,
            audit: false
        }
    },

    // 只允许用核心节点，不装载外部 npm 节点，保证在别的机器上也能导入运行
    functionExternalModules: false,

    // 关掉遥测
    telemetry: false
};
