# MVP-06 网络创建与共享查询

- 状态：已完成
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

- [x] 先落 pending 映射，再调用独占 Session 创建 SDK 网络，最后写回状态。
- [x] 读取网络列表只读本应用管理的网络；外部已有网络不自动导入。
- [x] 对 SDK 成功/数据库失败按固定 engine_name 对账，不重复创建。
- [x] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_team_shares_network：不同用户看见同一资源。
- test_same_label_different_identity：显示名不使 SDK 网络冲突。
- test_create_writeback_failure：失败可对账且保留诊断。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做网络删除、外部网络自动接管或设备发现。

## 完成记录

2026-09-25 完成网络 API/service/controller/repository、数据库引擎独占槽位、每次独占 SDK Session、最小幂等预留与迁移 0003。不同成员共享应用网络，同名保持不同 UUID；pending 先落库、SDK 后写回，同键恢复原内部名称。业务失败回传自动生成的 Idempotency-Key；引擎未知返回 ENGINE_STATE_UNKNOWN 且不可自动重试。

仓库根执行 `web/backend/.venv/bin/python web/scripts/lab.py seed` 和 `web/backend/.venv/bin/python web/scripts/lab.py verify`：MVP-01～06 累计 **120 passed、0 skipped**，包含10项网络测试和真实 HTTP 网络冒烟；r1/r2 与 Cisco 四设备基线均重新创建。backend 的 Ruff、`uv lock --check`、文档链接与 Git 空白检查通过。独立只读审查发现的未知状态分类已修复并复审。版本、源码摘要、逐项结果见 [证据](../../evidence/mvp-06-verification.json)。

累计实测修复了 MVP-02 空 API key 配置导致真实引擎401的问题，并将 MVP-04 登录限流恢复为原运行契约的账号/IP组合每分钟5次失败，均新增回归测试。网络初始化尚不创建快照；unknown 的管理员对账入口在 MVP-09 接入。没有修改 Java 引擎，失败注入没有冒充真实引擎故障。
