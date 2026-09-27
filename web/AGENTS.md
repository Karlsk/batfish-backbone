# Batfish Web 项目规范

本文件适用于 `web/` 下的设计、后端、前端和测试。执行项目级 `spec-dev` 时，即使从仓库根目录启动，也先读取本文件。这里规定长期约束；具体交付物、依赖与验收以目标 spec 为准。

## 范围与事实来源

- 文档入口：[docs/README.md](docs/README.md)。研发流程：[docs/development-workflow.md](docs/development-workflow.md)。
- 需求单元位于 `docs/changeloge/mvp/`、`docs/changeloge/advance/` 和 `docs/changeloge/leader/`；保留 `changeloge` 拼写，不另建平行目录。
- 一次默认实现一份 spec，单份目标不超过 2 人天；超出时拆成可独立验收的子项并更新依赖，不能删减验收来压缩工作量。
- MVP-25 通过后进入第二阶段；ADV-10 通过后进入第三阶段；领导端以 ADV-18 的完整验收为前置。文档存在、任务勾选、mock 通过均不等于阶段验收通过。
- 团队内网共享所有网络、快照及分析结果；账号内置、管理员创建、无公开注册，角色为管理员/普通成员。共享资源不意味着共享可变 SDK 上下文。
- 已确认的 spec 可直接执行；只对影响范围、接口或验收的未决事项提问，避免重新确认已确定的技术选型。

## 后端分层

技术栈和模块图以 [architecture.md](docs/architecture.md) 为准：FastAPI、Pydantic、Pybatfish、SQLAlchemy/Alembic、PostgreSQL，独立 Python worker。

```text
api → service → controller → Pybatfish
        ↓
本模块 repository / 文件存储
```

- api：输入校验、提取可信身份、调用 service、映射 HTTP 响应；不放业务编排或 SDK 操作。
- service：业务权限、资源生命周期、任务编排、参数归一化和结果摘要；使用公共 DTO，不返回 SDK 对象。
- controller：适配 SDK 参数、调用公开能力、转换 SDK 结果和底层异常；这里不是 HTTP controller。
- 跨业务模块只通过对方 service 对接；不导入对方 controller/repository/内部 ORM，不形成循环依赖。公共 contracts、基础设施和装配入口按架构文档使用。
- repository 是模块内部持久化实现，不是第四个跨模块业务入口。无 SDK 操作的模块不必创建空 controller。
- Pybatfish 只由 controller、基础设施 session factory 及 SDK 兼容性测试直接使用。Web 前端不直连引擎。

## 接口与 SDK 语义

- 最小必要参数显式声明；专家扩展使用有类型、有白名单的 `options`，按 [api-contracts.md](docs/api-contracts.md) 校验后在 controller 展开为 SDK kwargs。
- 拒绝未知参数、重复冲突和 network/snapshot/host 等上下文覆盖；不提供任意 Python、方法名反射或私有 SDK 透传。
- 每个执行任务独占一个 Session，任务内复用，任务之间不共享可变 network/snapshot；资源上下文来自服务端映射。
- 首个 SDK 候选版本和实际兼容结论以 MVP-01 报告为准；锁定本仓库引擎 revision 与 SDK/Python 版本。不得换成官方 latest 来掩盖当前分支兼容问题。
- 快照不可变，初始化 `overwrite=false`；重试使用新内部名称，不覆盖原始快照。
- 所有 SDK 工作遵循同一引擎串行执行约束。长任务由独立 worker 处理，不用 FastAPI 进程内临时任务承载。
- 仅未开始的任务可取消；客户端超时、worker 失联不等于引擎停止。引擎状态未知时保留占用、阻止重复调度，按运行文档对账。
- PostgreSQL 保存业务元数据，文件卷保存上传和结果；不直接读写 Batfish 内部存储。

## 前端与结果展示

采用 React、TypeScript、Vite、Ant Design、TanStack Query；交互遵循 [frontend.md](docs/frontend.md)。

- 默认表单只展示必要字段，高级参数折叠显示；折叠不清空参数，展示已生效数量。基础/专家模式共享接口、校验和状态。
- 按“结论 → 证据 → 原始信息”展示，详情抽屉和按需加载承载次要内容。模型限制、解析警告、截断信息在结论层可见。
- 查询键包含 network/snapshot 及有效参数；切换上下文后旧响应不能覆盖新结果。
- 区分空结果、不可达、未支持、失败、任务中断；不把所有非成功状态都表现为空表格。
- 虚拟 traceroute 是模型推演，不代表在线探测或回程证明。华为/H3C 未覆盖能力不能显示为已验证。
- Cookie/CSRF 和 OpenAPI 生成类型按契约执行，不把长期 token 或引擎地址放进浏览器持久化配置。

## 实施、验证和完成记录

- 先检查目标 spec 的前置交付物及验证证据，再按相关技术栈执行；不能套用其他项目的 Go/Gin/goose 命令。
- MVP-01 使用临时 Python/SDK 环境验证，不依赖 MVP-02 尚未创建的 pyproject；具体命令见该 spec。
- 后端重点测试权限、options、任务状态、SDK 映射和结果语义；持久化与队列行为使用隔离 PostgreSQL 验证。
- 前端使用实际 package scripts、Vitest、构建/类型检查；闭环验收使用 Playwright 与页面检查。不存在的脚本先按本项范围建立，不能声称已运行。
- SDK 集成连接固定版本的隔离测试引擎；只用公开或合成样例，不复制私有设备配置和认证材料。
- mock 可支持业务测试，不能替代 spec 要求的真实引擎验证。缺环境时明确记录“待验证/未通过”，不标完成，不放行依赖该证据的后续项。
- 运行目标 spec 要求及影响范围内的检查；未修改 Java 引擎时不强制每个 Web 增量跑全量 Java 测试。纯文档/视觉改动使用对应检查，不编写镜像式测试。
- 及时在 spec、阶段索引及受影响的总索引同步实际状态与证据；仅必需检查全通过后才标记“已完成”。记录日期、实际文件、命令/工作目录、结果、引擎/SDK版本和剩余限制；未运行、失败和通过明确区分。
- 默认不自动提交、推送、合并或部署；保留用户已有改动。用户启动 `mvp-runner` 并授权“逐篇验收后提交、继续”时，由 runner 在当前及此前所有 MVP 必需验收通过后提交并继续，无需逐篇再确认；该授权不包含推送、合并或共享/生产发布。仅生成或检查技能不启动批次。若需要新建开发分支，默认使用 `codex/` 前缀并遵循用户指定的工作区安排。
- 连续 MVP 回归使用 [测试环境](docs/test-lab.md) 中 r1/r2 与 Cisco 四设备配置。需要真实运行应用、数据库和 Batfish；不需要真实路由器或现场转发结果对照。浏览器验证随已实现页面及 spec 要求加入，不能用后端 pytest 替代前端/部署验收。
- 领导端与技术端在同一前端项目中保持独立路由和壳层，共用认证及后端契约；领导端汇总不能把“未检查”“范围外”或“模型限制”写成健康结论。LDR 逐篇验收、提交与继续由用户已授权的本批次主流程执行，单篇 `spec-dev` 仍只负责当前规格。
