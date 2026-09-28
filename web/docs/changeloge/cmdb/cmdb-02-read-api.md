# CMDB-02 快照级资产与历史只读 API

- 状态：待开发；阶段：采集一期；依赖：[CMDB-01](cmdb-01-identity-revisions.md)；预计：2.5 人天。

## 交付与接口

提供 `GET /api/v1/networks/{network_id}/cmdb/snapshots`、`/snapshots/{snapshot_id}/devices`、`/devices/{device_id}`、`/devices/{device_id}/history`、`/links` 的分页读接口。设备返回稳定 ID、该快照的名称/型号/地址/来源、配置引用与字段 `known/unknown` 状态；历史按采集时间和快照 ID 排序，不将采集失败记录当作当前版本。列表可按设备名/站点/角色筛选，查询只读数据库，不同步调用 SDK。包含历史 `snapshot_id` 的资源读取必须验证其属于同一网络。保留现有用户共享读取权限。

## 验收

双网络同名设备、旧/新快照切换、同 hostname 管理 IP 变化保持历史关联、改名设备作为新身份展示、失效快照、分页稳定排序、未提供 CMDB 的旧 ZIP、成员/匿名访问均有 HTTP 契约测试。生成前端 OpenAPI 类型并核对错误码；未实现写入或图形画布。
