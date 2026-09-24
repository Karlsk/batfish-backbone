# MVP-06 网络创建与共享查询

- 状态：待开发
- 阶段：1
- 依赖：[MVP-05](../mvp/mvp-05-user-administration.md)
- 预计工作量：1.0 人天（实现/验证 0.5 + 测试 0.25 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

全团队成员能够创建并查看逻辑网络，内部身份保持稳定。

- 网络创建/列表/详情、SDK 名称映射与 pending/ready/failed 对账。

## 设计与接口

- GET/POST /networks；GET /networks/{id}。
- NetworksService.require_ready(actor, network_id) → NetworkDTO；NetworkController.create(engine_name) 仅操作 SDK。
- 内部 UUID/name 唯一，display_name 不是跨模块引用键。
- 同步创建通过 SDK factory 的共享引擎锁；锁忙时503并保留 pending。相同创建幂等键复用原资源并尝试恢复，不创建新的内部名称。引擎锁接口先建立，worker 在 MVP-09 复用。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/networks/api.py`
- `web/backend/app/modules/networks/service.py`
- `web/backend/app/modules/networks/controller.py`
- `web/backend/app/modules/networks/repository.py`
- `web/backend/tests/test_networks.py`

## 实施步骤

- [ ] 先落 pending 映射，再调用独占 Session 创建 SDK 网络，最后写回状态。
- [ ] 读取网络列表只读本应用管理的网络；外部已有网络不自动导入。
- [ ] 对 SDK 成功/数据库失败按固定 engine_name 对账，不重复创建。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_team_shares_network：不同用户看见同一资源。
- test_same_label_different_identity：显示名不使 SDK 网络冲突。
- test_create_writeback_failure：失败可对账且保留诊断。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做网络删除、外部网络自动接管或设备发现。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
