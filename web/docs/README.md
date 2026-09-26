# Batfish Web 文档入口

日期：2026-09-26。状态：MVP-01～25 已完成，第一阶段真实服务、两套配置、双用户浏览器与部署恢复验收通过。已交付认证、上传/初始化、诊断、设备/接口、路由/LPM、虚拟 traceroute、任务、导出、资源删除及前端；ADV-01～07 已完成（拓扑接口/页面、BGP模型会话接口/工作台及ACL流量测试、条件搜索与无效规则接口），ADV-08～18 待开发。详见 [首版验收报告](mvp-acceptance.md)。

## 已确认的需求

- 为当前 Batfish 仓库增加 Web 工作台，网络人员无需编写 Python 或使用 Notebook。
- 团队内网共享；所有成员共享网络、快照和分析结果，不做项目级数据隔离。
- 内置账号密码，管理员创建账号，无公开注册；普通成员与管理员两种角色。
- 后端遵循 `api → service → controller → Pybatfish`；跨业务模块只调用对方 service。
- 常用接口采用最小必要参数，专家通过经过校验的扩展参数获得灵活性。
- 前端美观简洁，基础操作与高级参数并存；结论、证据、原始信息逐层展开。
- 第一阶段实现基础排障闭环；第二、三阶段也提前编写开发 spec，首版验证通过后继续开发。
- 每份 spec 以不超过 2 人天为拆分目标，包含实现、必要测试及文档更新。
- 使用用户指定的目录名 `changeloge`，不另建 `changelog` 平行目录。

## 阅读顺序

1. [产品设计与需求评估](design.md)：范围、用户流程、合理性评估及阶段边界。
2. [技术架构](architecture.md)：分层、模块依赖、SDK 接入和任务执行。
3. [API 与数据契约](api-contracts.md)：身份、参数、接口、数据模型与错误。
4. [前端交互规范](frontend.md)：视觉、基础/高级模式和逐级展示。
5. [运行与部署设计](operations.md)：资源、配置、恢复与版本绑定。
6. [验证与验收](validation.md)：SDK 对照、多用户隔离和阶段门槛。
7. [SDK 能力覆盖表](sdk-coverage.md)：专用功能、专家入口和未纳入范围的能力。
8. [研发规格索引](changeloge/README.md)：完整顺序、依赖和工作量。
9. [开发工作流](development-workflow.md)：项目级 spec-dev、Superpowers 与 grill-me 的分工及调用方式。
10. [SDK 兼容性实测报告](sdk-compatibility.md)：MVP-01 版本、契约、测试证据和复现步骤。
11. [本机功能测试环境](test-lab.md)：真实服务启动、r1/r2 与 Cisco 四设备配置快照、冒烟和累计回归入口。
12. [技术工作台双主题设计](plans/2026-09-26-technical-workbench-design.md)：已完成现有前端深浅主题升级；[实施计划](plans/2026-09-26-technical-workbench-implementation.md)与[验收记录](evidence/technical-workbench-theme-2026-09-26.md)。本次双主题范围已完成；用户后续已授权进入 ADV，领导端另行安排。

## 目录与实施方式

```text
web/docs/
├── README.md
├── design.md
├── architecture.md
├── api-contracts.md
├── frontend.md
├── operations.md
├── validation.md
├── sdk-coverage.md
├── development-workflow.md
└── changeloge/
    ├── README.md
    ├── mvp/       # 阶段 1，MVP 编号
    └── advance/   # 阶段 2、3，ADV 编号
```

spec 是后续实施的需求、设计和验收单元，不是完成日志。所有 spec 初始状态为“待开发”；开发时先读共享契约与依赖 spec，再按本项范围实现。验收后在该 spec 中补充实际改动、验证命令/结果与剩余限制，并更新索引状态。不要因为文档已存在就跳过前置依赖或宣称功能可用。

开始顺序为 MVP-01；第一阶段最终门槛为 MVP-25。阶段 2 从 ADV-01 开始，阶段 3 从 ADV-11 开始。一次只安排已满足依赖的 spec。SDK 兼容性验证失败时修订受影响设计，不用浏览器直连或私有 SDK 方法绕过约束。

## 尚未实测的规划假设

暂按 10～20 位团队成员、单快照约 100 台设备规划；这不是容量承诺。单 Batfish 实例的重任务默认串行，用户请求可排队。采用单机应用部署，PostgreSQL 保存账号和任务，文件卷保存原始上传及结果，Batfish 保有自身存储。硬件和实际耗时在 MVP-01、MVP-25 中记录并校准。

工作量是熟悉项目的开发者在依赖就绪后的估算，1 人天按 8 小时计算，不是日历工期承诺。若某项评估超过 2 人天，应先拆成有独立验收标准的子 spec，再编码；不能通过省略测试、恢复语义或权限检查压缩估算。

当前已完成设计/spec 文档、项目规范、项目级技能、MVP-01 集成测试与兼容性报告，以及 MVP-02 后端基础应用、MVP-03 数据库迁移与受控文件存储、MVP-04 登录与会话管理、MVP-05 账号管理与审计、MVP-06 共享网络管理、MVP-07 配置上传与安全校验、MVP-08 任务记录与排队取消、MVP-09 独立worker与保守恢复、MVP-10 不可变快照初始化、MVP-11 解析诊断与原始文件查看、MVP-12 能力目录与结果基础、MVP-13 设备与接口分析、MVP-14 路由与LPM、MVP-15 IPv4单向虚拟traceroute。启动方式见 [后端 README](../backend/README.md)。新锁文件已复验真实 SDK 基线，没有修改 Java 引擎；尚未实现具体前端业务页面、导出、清理与部署；整体交付仍以MVP-25验收为准。

最新进阶交付：[ADV-01拓扑接口验收](evidence/adv-01-verification.md)、[ADV-02可交互拓扑验收](evidence/adv-02-verification.md)、[ADV-03 BGP接口验收](evidence/adv-03-verification.md)、[ADV-04 BGP页面验收](evidence/adv-04-verification.md)、[ADV-05 ACL接口验收](evidence/adv-05-verification.md)、[ADV-06 ACL页面验收](evidence/adv-06-verification.md)、[ADV-07 ACL搜索接口验收](evidence/adv-07-verification.md)。
