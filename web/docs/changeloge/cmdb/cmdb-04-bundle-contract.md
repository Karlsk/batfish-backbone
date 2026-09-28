# CMDB-04 统一 ZIP、node.json 与物理链路校验

- 状态：待开发；阶段：采集一期；依赖：[CMDB-01](cmdb-01-identity-revisions.md)；预计：2.5 人天。

## 交付与接口

扩展现有 ZIP 解包验证：保留 `configs/`，新包在根目录带版本化 `node.json`，物理链路放 `batfish/layer1_topology.json`。`node.json` 每台至少 `hostname/config_path`；同采集源内规范化 hostname 唯一，配置路径唯一并对应实际文件；可选厂商、型号、管理地址、站点、角色和标签，管理 IP 不参与身份匹配。Web 分配内部 `device_id`。Layer-1 `edges[]` 两端使用 Batfish 的 `hostname/interfaceName`，重复边规范化、悬空节点和接口冲突产生定位明确的错误/告警。拒绝路径穿越、ZIP bomb、未知 schema_version 与不兼容字符编码；保留原有总量限制。Web 私有元数据不送 SDK。旧仅配置 ZIP 继续成功，但无 CMDB/L1 结论。

## 验收

真实 r1/r2、Cisco 四设备合成 ZIP 增加节点和 L1 链路，验证哈希、节点/配置/拓扑关联及 SDK 初始化；空或非法 hostname、大小写重复、文件、边、过大/截断/重传包拒绝且不留下半成品。文档给出可直接制作的示例 ZIP 与 JSON。
