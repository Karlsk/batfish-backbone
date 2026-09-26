# ADV-01 拓扑接口验证

日期：2026-09-26；基线提交：`b59995435c`（MVP全部复验及双主题升级）。状态：已通过全部本篇必需验收及影响范围累计回归。

## 实现范围

- POST `/api/v1/networks/{network_id}/snapshots/{snapshot_id}/analyses/topology`，默认layer3，支持bgp/ospf/isis及typed节点/邻居选择。
- GET `/api/v1/results/{id}/graph`，保存来源、方向、接口、SDK原始属性和孤立节点，按focus/hops/limit读取，明确scope/truncated。
- 同一任务内复用一个Session顺序查询；继承权限、幂等、上下文、队列、版本缓存和模型警告。整体等待预算耗尽后不提交下一个问题。
- graph持久化受节点/边及字节限额约束，无悬空边；JSON导出支持图，CSV返回409。不增加依赖或数据库迁移。
- 仅后端接口和生成的前端类型；可交互拓扑页面属于ADV-02。

## 验收覆盖

`tests/test_topology.py`包含：注册与参数白名单、稳定双向/并行边ID、孤立节点、邻域距离、节点/边/字节限制、存储截断传播、等待预算、同Session及第二个问题的确定失败/未知结果占用语义。

真实集成使用固定分支引擎与r1/r2、Cisco四设备，另用Cisco配置派生BGP和ISIS关系并加入孤立设备。每个样例四视图，独立序列化SDK原始行与图边属性逐行比对，同时验证节点、过滤、缓存复用和view/options缓存隔离、读取错误与导出。派生样例要求四视图均非空，避免空结果误当协议适配通过。真实HTTP+独立worker冒烟额外运行两套拓扑layer3接口。

静态分层守卫只放行service调用本模块graph纯函数，保留API直调、graph访问SDK、跨模块直调graph等禁止规则。

## 开发及审查记录

- 初始5项测试因缺少拓扑功能失败，随后通过。
- 初版SDK对照测试误用不存在的to_json方法；修正为独立dict序列化，三套样例四视图通过，未改变产品来迁就测试。
- 预算回归先失败（仍提交下一条问题），共享deadline修复后通过。
- 独立只读审查未发现实现逻辑缺陷；指出公共契约缺少新增字段及边界，已补齐；其建议的Session/后续问题失败、独立边限额、缓存测试已加入。
- 首次累计302项中301通过，唯一失败为新增graph文件未登记分层白名单；补充精确规则及5项守卫测试后重跑完整套件。

## 环境与边界

运行目录：`web/.runtime/test-lab/c3e540b4ca7c`；API 18000、Batfish 19996、PostgreSQL 15439，迁移0008。引擎revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，SDK `2026.9.17.3748`，Python `3.12.12`。

验证配置模型功能，不对照现场转发；没有新增100设备容量结论。协议关系不表示会话健康，缺少边不证明物理断线。Java引擎未改动。MVP部署/备份恢复证据属于前置提交，本篇不将旧生产镜像声明为包含ADV-01。

## 最终命令与结果

以下命令在仓库根执行（pnpm命令在web/frontend执行），均使用项目锁定环境：

| 检查 | 实际命令 | 结果 |
| --- | --- | --- |
| 完整后端/SDK/数据库/HTTP | `web/backend/.venv/bin/python web/scripts/lab.py verify` | 307 passed、0 skipped，195.81s；checks/549d876f5735 |
| 独立真实服务冒烟 | `web/backend/.venv/bin/python web/scripts/lab.py smoke` | 12 passed；按smoke筛选有意排除295；checks/f14819cd3a0c |
| 前端单测 | `pnpm test` | 47 passed / 17 files |
| 类型及构建 | `pnpm build` | 通过；保留既有大于500kB chunk提示 |
| 生成类型一致性 | `pnpm check:api` | 通过 |
| 前端格式 | `pnpm format:check` | 通过 |
| Python静态检查 | `web/backend/.venv/bin/ruff check web/backend web/scripts web/deploy` | 通过 |
| 现有页面浏览器回归 | `pnpm exec playwright test --output=../.runtime/adv01-browser` | 14 passed、0 skipped、0 flaky，2.8m |
| 文档及空白 | 本地Markdown链接检查、`git diff --check` | 通过 |

后端的两个警告分别为既有Starlette/httpx弃用提示、ZIP重复名拒绝测试故意构造的警告，不是跳过。运行日志在忽略提交的 `web/.runtime/adv01-*.log`，凭据不进入文档。

[机器证据与完整源码指纹](adv-01-verification.json)。本篇实现保留未提交，未自动进入ADV-02。

## ADV连续批次提交前累计门槛

用户明确授权ADV-01～18逐篇验收后提交。源码指纹与上述实现一致；重新全量后端307、冒烟12、前端47、常规浏览器14通过；新目录`deploy-adv01-batch`完整HTTPS/worker失联/重启/三卷备份/新项目恢复通过，恢复后light/dark各3项部署及1项双用户浏览器通过，0跳过/重试成功。已检查恢复后深色结果截图。锁文件、静态检查、构建、API类型、格式与文档检查通过。本批镜像已包含ADV-01，旧轮次“未重建镜像/未提交”仅为当时状态。
