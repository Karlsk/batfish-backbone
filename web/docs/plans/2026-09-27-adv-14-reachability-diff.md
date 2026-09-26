# ADV-14 差异可达性实施计划

> 按 `spec-dev`、TDD 和累计 runner 门槛执行；本篇通过后单独提交并进入 ADV-15。

**目标：** 对固定比较记录、明确目的地址和起点及可选流量范围，返回候选相对基线新增或消失的可达示例和两侧路径。

**架构：** changes service 校验比较身份与范围，持久化带双快照上下文的任务；analysis service/controller 在独占 SDK Session 中调用 differentialReachability，并把返回的 flow、两侧 traces、disposition 和方向转换为公共结构。ResultsService 对示例和截断做有界存储、分页与导出。

**技术：** FastAPI、Pydantic、Pybatfish HeaderConstraints/PathConstraints、PostgreSQL、固定 Batfish 引擎、Pytest、OpenAPI 类型生成。

**规格：** [ADV-14](../changeloge/advance/adv-14-differential-reachability.md)、[API 契约](../api-contracts.md)。基线提交 `72ca4b2491`。

## 共同约束

- `destination_ips`、`start_location` 必填并非全网默认；candidate 是 SDK snapshot，baseline 是 reference_snapshot。
- `source_ips`、`ip_protocols`、`destination_ports`、`max_traces` 是白名单专家参数；端口仅 TCP/UDP，IPv4/整数范围严格校验。
- 用实测双侧 flow 与 trace dispositions 判定方向；路径变化而双侧可达状态相同不应称为新增/消失。
- 样例数量不是全量受影响业务数；两侧 traces、原始计数、截断和覆盖限制必须可见。
- 所有 SDK 操作走 analysis controller；changes 只经 analysis.service 调用，不越层访问 SDK。

## 审查重点

- 未知/无效起点和空目的 IP 范围，返回明确验证或执行错误，不能变成“无影响”。
- 一侧 ACCEPTED、另一侧 DENIED/NO_ROUTE/NULL_ROUTED 与混合路径的方向；多个 trace disposition 的边界。
- 对称双快照查询方向，比较删除/版本变化后新任务失败而旧结果可读。
- `max_traces` 或结果字节/行数限额造成的部分证据必须标记，不能隐藏为完整回答。
- 未采样到流或不同路径但可达性相同时，只说明当前限定范围未找到可达性变化。

## 步骤

- [x] 以可控 Cisco ACL/路由变化直接调用当前 SDK，记录双侧 trace 列、实际差异方向与截断语义；先写失败测试。
- [x] 增加有类型请求/白名单参数验证，并测试缺范围、端口约束和上下文覆盖拒绝。
- [x] 在 analysis controller 适配 SDK，并在 changes service 绑定不可变比较、任务/缓存/结果发布；保留两侧 flow 证据。
- [x] 加入真实 API/独立 worker 冒烟、OpenAPI 类型，完成定向及累计后端/前端/浏览器/HTTPS 恢复门槛。
- [x] 自审模型边界、错误/权限、截断和多用户隔离；回写 spec、索引、契约与证据，独立提交。
