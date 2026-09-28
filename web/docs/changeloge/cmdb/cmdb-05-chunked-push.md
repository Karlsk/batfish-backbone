# CMDB-05 分段推送与采集会话

- 状态：待开发；阶段：采集一期；依赖：[CMDB-04](cmdb-04-bundle-contract.md)；预计：3 人天。

## 交付与接口

专用采集凭证按网络授权：`POST /api/v1/networks/{id}/collection-runs` 创建会话（`source_id,collection_id,collected_at,total_bytes,sha256,chunk_size`），`PUT /{run_id}/chunks/{index}` 传二进制与分段哈希，`GET /{run_id}` 查询缺段与状态，`POST /{run_id}/finalize` 请求完成，`DELETE /{run_id}` 放弃未完成会话。采集平台负责定时和控制器适配；Web 不拉控制器。相同源/ID/哈希重放返回原会话，不同摘要冲突；超时可续传，分段乱序/重复可控。每段、总量、并发、过期与磁盘占用均限额；落盘原子并定期清理过期未引用临时文件。`finalize` 尚不晋升快照，交给 CMDB-06。

## 验收

双采集凭证权限、断点续传、乱序、重复相同/不同块、并发完成、校验失败、掉电恢复、到期清理及 CSRF/令牌边界均在真实 API/文件卷测试；不覆盖现有浏览器 ZIP 通道。
