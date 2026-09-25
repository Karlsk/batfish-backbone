# MVP-16 前端实施计划

基线42f7aea7f5。采用已确认的中文浅色桌面工作台设计，固定侧栏和顶部网络/快照上下文；本篇建立骨架和公共组件，具体登录与业务页面按后续spec开放。

1. 建立React/TypeScript/Vite、Ant Design、TanStack Query和路由项目，锁定实际依赖版本；先建Vitest/Testing Library及Playwright验证入口。
2. 从装配后的FastAPI OpenAPI离线生成类型并提交；增加生成一致性检查。请求只访问同源/api/v1，Cookie随请求，CSRF仅存内存；统一安全错误；身份变化清缓存，不存长期token。
3. 上下文Provider在切换网络时清空快照，所有资源查询key包含network/snapshot/result/有效参数；验证旧请求晚返回不能覆盖新上下文。未来页面只能使用登记路由，不按服务端任意能力名生成执行入口。
4. 先写AdvancedOptions折叠保留值/数量、ResultSummary覆盖/截断/ignore_filters、DetailsDrawer按需加载、错误与空态测试，再完成公共组件；主题token和焦点样式统一。
5. 真实浏览器检查1280/1920布局、中文长名称和键盘焦点；组件案例通过独立浏览器测试harness使用真实组件，不把模拟数据称为后端闭环。实际工作台连接运行中的API健康入口。
6. 独立只读审查，累计后端259项（新增时按实计）、真实SDK/HTTP冒烟、前端单测/类型/构建/OpenAPI一致性/浏览器验收，记录源码指纹与证据后提交，继续MVP-17认证页面。

参考公开文档：[Vite](https://vite.dev/guide/)、[Ant Design](https://ant.design/docs/react/getting-started/)、[TanStack Query](https://tanstack.com/query/latest/docs/framework/react/reference/index)、[OpenAPI TypeScript](https://openapi-ts.dev/cli)。依赖最终版本以package.json和pnpm-lock.yaml为准。
