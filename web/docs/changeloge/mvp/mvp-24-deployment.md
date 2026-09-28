# MVP-24 单机团队部署与运行手册

- 状态：已完成
- 阶段：1
- 依赖：[MVP-23](../mvp/mvp-23-resource-deletion.md)
- 预计工作量：1.5 人天（实现/验证 1.0 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

提供可复现的 Web/API/worker/数据库部署并连接当前分支引擎。

- 容器/反向代理、依赖健康检查、管理员初始化、持久卷、版本和恢复说明。

## 设计与接口

- 部署单元及参数使用 operations.md；生产入口同域 HTTPS。
- Batfish 构建使用当前分支 JAR 或已验证定制镜像，模板路径必须包含所需目录。
- 生成实际可执行的运行 README，不把本文设计示例当已存在命令。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/deploy/compose.yaml`
- `web/deploy/proxy.conf`
- `web/backend/Dockerfile`
- `web/frontend/Dockerfile`
- `web/README.md`
- `web/docs/deployment-validation.md`

## 实施步骤

- [x] 打包应用与静态资源，配置 API/worker 分进程和只读代码。
- [x] 设置卷、健康检查、配置注入和一次性管理员初始化说明。
- [x] 完成启动/停止/备份/恢复/未知任务对账演练，记录引擎构建来源。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- 全新目录部署后登录、网络创建和样例初始化成功。
- 重启 API 不丢任务；worker 失联按设计阻塞未知引擎。
- 数据库/SDK端口不暴露在普通访问入口，浏览器无 SDK key。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做 Kubernetes、高可用、自动发布或外部公网部署。

## 完成记录

2026-09-26完成Compose同域HTTPS部署：固定digest的Python/Node/Nginx/Postgres/Java基础镜像，固定SDK/前端锁，当前分支JAR+模板摘要。API/worker分进程非root、只读代码，数据库/SDK不发布端口；私有state注入配置/证书，当时无默认管理员密码。交付backend/frontend Dockerfile、deploy/compose.yaml、proxy.conf、engine健康与volume_archive、scripts/deploy.py和verify_deployment.py、web/README.md。默认凭据规则已在 2026-09-28 [后续修订](../../evidence/default-admin-bootstrap-2026-09-28.md)。

真实部署发现MVP-07/10上传允许附带README而SDK目录重建拒绝的缺陷，修复为复用safe_path规范验证，保留哈希/UUID边界，新增合法附带输入和越界拒绝回归。恢复修正tar data_filter丢目录模式/属主问题，启动前恢复UID10001与目录0700/文件0600。

全新目录实测HTTPS管理员初始化/改密、Cookie安全属性、两套ZIP初始化/nodes、API重启任务保留。SDK请求在途强制终止本测试worker后unknown保持，跨多轮询分析只queued不执行；停止worker、重启引擎并管理员审计对账后恢复。离线同时备份DB/应用/引擎卷，恢复到新项目空卷，原登录/任务/结果/导出和两快照新interfaces查询均通过；HTTPS生产包浏览器1项及视觉检查通过。

累计后端287、前端37、常规浏览器10、部署浏览器1通过，0skip；smoke12，Ruff/锁/OpenAPI/类型/构建/格式/链接通过。独立只读审查最终无阻塞。详见 [部署验证](../../deployment-validation.md)、[机器证据](../../evidence/mvp-24-verification.json)。只验证2/4台合成配置；本机证书自签、镜像恢复需相同ID、无在线增量/HA/跨版本自动回滚。满足MVP-25依赖。
