# CMDB-01 稳定身份与资产版本模型

- 状态：待开发；阶段：采集一期；依赖：LDR-12；预计：3 人天。
- 共享约束：[设计](../../cmdb-simulation-design.md)、[架构](../../architecture.md)、[验收](../../validation.md)。

## 交付与接口

以现有 `network_id`、`snapshot_id` 为锚，建立采集源、稳定内部 `DeviceIdentity` UUID、不可变 `DeviceRevision`、`PhysicalLinkRevision`、`ConfigArtifact` 和 `CollectionRun` 的 DTO、ORM 与空库迁移。一期按 `(network_id,source_id,hostname_key)` 唯一定位采集设备；`hostname_key` 由原始 hostname 去首尾空白并做大小写规范化，保留完整后缀。人工设备由 Web 生成 ID。配置正文仍在文件卷，数据库只存引用/哈希/有限索引。每条版本记录保留来源、采集时间、快照、内容哈希和状态；管理 IP 改变不换内部身份，hostname 改名默认形成新身份且不自动合并历史，跨网络绝不复用 ID。旧快照不重写；历史已有配置 ZIP 用“无 CMDB 元数据”状态兼容。`CollectionRun` 尚不负责上传执行。

## 验收

在隔离 PostgreSQL 上测试空库迁移与回退、网络隔离、同源规范化 hostname 冲突、大小写变化与管理 IP 变化保持同一内部 ID、hostname 真正改名产生新 ID、跨采集源同名不合并、版本不可变及旧快照读取；同步架构规则与迁移文档。`api → service → controller` 及跨模块 service 边界继续生效。仅模型与迁移，不声明已打通采集。
