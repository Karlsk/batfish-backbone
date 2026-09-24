# ADV-12 配置文件差异分析

- 状态：待开发
- 阶段：3
- 依赖：[ADV-11](../advance/adv-11-comparison-context.md)
- 预计工作量：2.0 人天（实现/验证 1.25 + 测试 0.5 + 文档/自检 0.25），依赖就绪后计；超过 2 人天先拆分。
- 共享约束：[架构](../../architecture.md)、[API 契约](../../api-contracts.md)、[前端规范](../../frontend.md)、[运行设计](../../operations.md)、[验收](../../validation.md)。

## 需求与目标

用户可以查看两个完整快照的文件新增、删除和内容变化。

- 按相对文件路径匹配、逐行 diff、文件摘要、单文件详情接口。

## 设计与接口

- POST /comparisons/{id}/analyses/config-diff → job；GET result 使用 kind=diff。
- 文件路径相同视为同文件；rename 不自动推断；编码转换仅用于展示，原始字节不修改。
- 无文本差异不等于网络行为相同；终端噪声可导致文本变化，应如实标识。

沿用 api → service → controller；所有跨业务模块调用经过 service。非 SDK 存储由本模块 repository 负责。浏览器不接触 SDK 会话或连接参数。

## 预期改动位置

以下是实现时的目标路径，本次文档编写不创建代码文件：

- `web/backend/app/modules/changes/service.py`
- `web/backend/app/modules/changes/config_diff.py`
- `web/backend/app/modules/results/diff.py`
- `web/backend/tests/test_config_diff.py`

## 实施步骤

- [ ] 通过 snapshots.service 取得受控文件 manifest，不直接读取其他模块目录。
- [ ] 实现文件分类和带两侧行号的文本差异，超大文件按限额返回摘要。
- [ ] 保留编码/不可解码信息，不生成猜测性配置语义。
- [ ] 运行下述验证，记录实际命令与结果，更新本文及索引状态。

## 测试与验收

- test_added_removed_changed：三类文件与行号正确。
- test_encoding_and_line_endings：展示解码不改源字节。
- test_large_file_limits：截断明确，不声明完整 diff。

后端测试在 `web/backend` 下使用 `uv run pytest` 指定上述测试文件；集成测试连接版本固定的隔离 Batfish 测试网络，不操作团队生产网络。

验收成功同时要求：契约与文档一致、失败行为可解释、无跨层/跨模块越界、没有把 mock 验证宣称为真实 SDK 验证。共享约束中的身份、版本、模型覆盖和结果截断规则均适用。

## 非目标与实施边界

- 不做语义配置合并、重命名推断或自动修复脚本。

## 完成记录

当前尚未开发或运行本 spec 的产品测试。实施者完成后在本节记录实际文件、验证命令、结果、引擎/SDK版本（如涉及）和剩余限制；存在验收失败时保持未通过状态。
