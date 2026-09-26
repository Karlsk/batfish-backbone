# ADV-13 路由差异实施计划

> 按 `spec-dev`、TDD 和累计 runner 门槛逐项执行；本篇通过后单独提交并进入 ADV-14。

**目标：** 在已固定的比较上下文中按候选相对基线展示新增、消失及变化的路由，保留 SDK 原始差异和两侧值。

**架构：** changes 模块 service 负责比较权限、任务与缓存；changes controller 经独占 SDK Session 调用 routes differential。结果归一化为已有 table 结果，由 ResultsService 原子持久化、分页和导出。请求校验复用 `RoutesRequest`，候选/基线的内部名称只由比较上下文生成。

**技术：** FastAPI、Pydantic、Pybatfish、PostgreSQL、真实 Batfish 固定引擎、Pytest、OpenAPI 生成类型。

**规格：** [ADV-13](../changeloge/advance/adv-13-routing-diff.md)、[API 契约](../api-contracts.md)。基线提交 `daffc4a41c`。

## 共同约束

- 候选映射 `snapshot`，基线映射 `reference_snapshot`；SDK 原始标记方向必须用可控增删路由实测后写入转换逻辑与验收证据。
- 复用已确认的 `RoutesRequest` 校验、节点/VRF/前缀/协议选择器与输出限额；未知参数和上下文覆盖拒绝。
- 不能按前缀单键覆盖 ECMP 或多协议路由；保留 SDK 的完整键、两侧属性和原始标记。
- 当前引擎、Pybatfish、数据库和两套配置的真实累计验收不能被 mock 替代。

## 审查重点

- `routes` 模板文件的 `differential` 字段和 Java Answerer 能力不一致：以当前锁定引擎+SDK 的实际调用证明能否工作，必要时停止在可复核冲突，不伪造结果。
- 只有一侧有某条路由、同键属性变化、相同前缀多下一跳、空结果四类输出方向。
- 缓存键必须包含两侧摘要和过滤条件；删除比较后旧结果可读，新分析禁止。
- worker 失联时沿用未知状态栅栏；查询不可把 HTTP 失败当成空差异。
- 大结果按现有分页/导出保留截断标记，结论不得声明路由策略等价。

## 步骤

- [x] 用可控 Cisco 基线/候选快照直接调用当前 SDK `routes` differential，记录原始列、标记与实际方向，并为结果约定写失败测试。
- [x] 为 API 校验、幂等/权限/比较上下文、完整路由键、两侧值和空结果写失败测试。
- [x] 增加路由差异 controller 与归一化 DTO；service 按现有 job 生命周期、缓存、发布执行，composition 接线。
- [x] 增加真实 API/独立 worker 冒烟，生成 OpenAPI 类型，完成定向和累计后端/前端/浏览器/HTTPS 恢复门槛。
- [x] 自审架构与错误边界，回写 spec、阶段/总索引、契约、证据；只暂存本篇并独立提交。
