# Batfish 中文工作台

Node 25.6.1、pnpm 11.19.0；依赖精确锁定。TypeScript 5.9.3 符合 OpenAPI 生成器的 5.x peer 契约。后端环境先按 [测试环境](../docs/test-lab.md) 启动。

```sh
cd web/frontend
pnpm install --frozen-lockfile
pnpm dev
```

访问 `http://127.0.0.1:15173`，开发服务器将同源 `/api` 转给本机 API 的18000端口，不改写 Origin。登录页面在 MVP-17 接入；届时必须在后端显式允许前端 Origin。当前未开放导航保留禁用状态，不依据服务端能力名动态生成执行入口。

```sh
pnpm generate:api
pnpm check:api
pnpm test
pnpm typecheck
pnpm build
pnpm format:check
pnpm exec playwright install chromium
pnpm test:e2e
```

OpenAPI 生成从后端装配完整路由，使用惰性 PostgreSQL engine，不连接数据库、不读取测试账号。提交生成文件；API 变化时重新生成并校验。

会话和 CSRF 仅存内存，请求使用同源 Cookie。身份变化清空查询缓存并重建上下文；所有资源查询使用 `resourceKey(identity, context, operation, parameters, resultId)`。切换网络清空快照，不借用上一个查询的数据填充新上下文。历史结果展示自身来源。

公共组件：AdvancedOptions 折叠保留值/显示生效数量；ResultSummary 首层展示模型限制、截断和忽略 ACL；DetailsDrawer 在打开时请求；States 区分错误、加载与空态。

Playwright 连接真实运行 API；`tests/harness.html` 是仅用于开发验收的合成组件场景，生产构建入口只有 index.html。两种桌面宽度的截图在忽略提交的 test-results 中。当前基础包体积较大，后续具体页面采用路由按需加载；构建的体积提示不等于容量或性能验收。
