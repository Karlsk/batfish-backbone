# 版本化网络资产与变更推演设计（草案）

## 目标、评估与选择

把现有“手工上传配置再发起专业查询”改为两期闭环：一期由既有平台定时采集、分段推送，Web 接收后展示物理拓扑、设备配置与历史版本；二期在某个不可变基线之上编辑多设备候选配置，生成候选快照，并逐级检查 Underlay、业务连通性、路径和网段隔离。Web 不负责登录控制器或直接下发设备配置。

比较过三种边界：只给 ZIP 增加元数据文件开发较快，却不能妥善管理历史身份、分段重试和人工维护；Web 自己适配各控制器会重复现有采集平台；**采用版本化 CMDB + 统一推送契约**，由上游负责异构控制器解析，Web 负责验证、存储、快照与推演。每个网络只有经校验成功的采集批次才可成为“最新”，失败批次保留错误而不覆盖现有视图。人工维护通过独立草稿发布为新版本，不原地改写采集事实。

现有基础可复用：`networks/snapshots/uploads/jobs/results/changes/business_concerns` 的 service、不可变快照、双快照比较和技术端 Cytoscape 画布。现有 ZIP 仅保证 `configs/`，拓扑分析仅有模型 L3/BGP/OSPF/ISIS，尚无物理资产主数据与分段推送。`node.json` 是 **Web 自定义元数据**，Batfish 不识别；物理链路必须位于 `batfish/layer1_topology.json`。入口需校验两者并仅将 Batfish 支持的文件交给 SDK，不能把 Web 元数据当设备配置。

## 统一数据模型和事实来源

- `DeviceIdentity`：网络内稳定内部 UUID；根据用户确认的上游现实，以 `(network_id, source_id, hostname_key)` 为一期唯一身份键。`hostname_key` 对原始 hostname 去首尾空白并做不区分大小写规范化，保留完整域名/后缀，不按 IP 匹配。原始 hostname 仍逐版保存供展示；管理 IP 改变不换内部 ID。相同采集源里 hostname 改名默认生成新设备，旧新历史不自动合并；若需要关联改名前后设备，另立带审计的人工关联流程。人工设备使用平台生成 ID。跨采集源同名也不自动合并。
- `DeviceRevision`、`PhysicalLinkRevision`、`ConfigArtifact`：绑定 Web `snapshot_id`；分别保存采集字段及来源、两端设备/接口、配置文件的内容哈希和文件引用。配置正文保存在受控文件卷，数据库保存索引与有限解析事实。设备、链接和配置版本不可原地覆盖。
- `CollectionRun`：`source_id`、上游 `collection_id`、采集时间窗口、目标网络、完整性声明、总内容摘要、状态与诊断。唯一键防重放；同 ID 同摘要返回已有记录，不同摘要报冲突。只接受完整包晋升；缺失设备/配置、悬空链路或时间窗口不一致时标记有限/失败，不能静默显示健康。上传失败、引擎初始化失败均不移动最新就绪指针。
- `Observation` 与 `ModelResult` 分开：真实会话/接口状态如果以后推送，记录观测时间与来源；Batfish 推演结果只能叫模型结果。字段无显式值时保持 `unknown` / `device_default`，不猜默认值，也不把未知视为一致。
- 所有资源按网络隔离、登录成员只读，管理员和专用采集凭证可写各自范围；采集凭证不能调用人工管理接口。服务端审计采集、人工编辑、候选创建和检查。模块之间只走对方 service。

## ZIP 与分段推送

标准包保留 Batfish 原生目录，并新增 Web 元数据：

```text
snapshot.zip
├── node.json                         # Web schema_version=1；采集源/时间/设备数组
├── configs/c1.cfg                    # 一台设备一个明确的 config_path
├── configs/c2.cfg
└── batfish/layer1_topology.json      # Batfish 原生 edges 格式
```

`node.json` 每台设备至少含 `hostname`、`config_path`；可选 `management_ip`、`vendor`、`model`、`site`、`role`、`labels`。Web 根据所属网络、采集源和规范化 hostname 分配内部 `device_id`；采集方不必提供设备 ID。规范化后重复的 hostname 拒绝发布，IP 变化只产生设备新版本。未知字段不能作为 Batfish 事实。`layer1_topology.json` 的 `edges[]` 两端采用 `hostname`/`interfaceName`；Web 映射到内部设备 ID，保留原始端点、方向和来源，检测重复/冲突/悬空边。旧配置 ZIP 继续可上传，但显示“无采集资产/无物理拓扑”；不能据模型 L3 边伪造物理连线。供应商私有字段经上游适配到统一格式，版本升级显式演进，不在 Web 中为每个控制器写 webhook 解析器。

`node.json` 的无注释最小示例：

```json
{
  "schema_version": 1,
  "source_id": "controller-a",
  "collection_id": "2026-09-28T10:00:00Z-42",
  "collected_at": "2026-09-28T10:00:00Z",
  "devices": [
    {"hostname": "c1", "management_ip": "192.0.2.11", "config_path": "configs/c1.cfg", "vendor": "cisco"},
    {"hostname": "c2", "management_ip": "192.0.2.12", "config_path": "configs/c2.cfg", "vendor": "cisco"}
  ]
}
```

`batfish/layer1_topology.json` 的最小示例：

```json
{"edges": [{"node1": {"hostname": "c1", "interfaceName": "GigabitEthernet0/0"}, "node2": {"hostname": "c2", "interfaceName": "GigabitEthernet0/0"}}]}
```

推送方先创建 `CollectionRun`，声明压缩总长度、整体 SHA-256、采集时间和完整性；按固定尺寸上传编号分段，每段带 SHA-256。服务端接受同摘要重试、拒绝同编号不同内容、校验总长/总摘要后 `finalize`。`finalize` 幂等并由 worker 异步完成解压、索引、初始化和晋升。分段目录有容量、数量、超时和租期限制；只清理过期未完成会话，不清理已被快照引用的文件。继续保留现有单次 ZIP 上传及人工 API。默认总包上限沿用当前配置的 100 MiB 压缩/500 MiB 解压/5000 文件；分段改善传输可靠性而非取消总量限制，扩容前用目标规模压测。

## API 与页面

一期 API 按 `api → service → controller`：`GET /networks/{id}/cmdb/snapshots`、`GET /.../snapshots/{sid}/devices`、`GET /.../devices/{device_id}`、`GET /.../topology?layers=physical,...`、`GET /.../configs/{artifact_id}`（分页/模块段）和跨版本 diff；人工草稿的设备、链路、配置 CRUD；采集用 `/networks/{id}/collection-runs` 创建、分段 `PUT`、状态 `GET`、完成 `POST`。严格 DTO、分页与已验证的 `options`，无任意 SDK kwargs。身份、CSRF/采集令牌与错误码沿用 Web 公共约束。

入口选择网络与快照后，物理拓扑是画布底层；L3/BGP/OSPF/ISIS 作为来源明确的可开关叠层，缺结果时先提交后台分析，不能在 GET 中同步调用 SDK。悬停给简要设备卡，左击固定详情，右击显示“查看全量/模块配置、加入拟变更”；另有键盘/触屏可用的菜单按钮。拓扑节点与配置用 `device_id` 关联，不用展示名作为键。历史切换同步刷新全部图层、详情和配置；可比较两版但不混用数据。底部“变更推演”只有草稿中所有已选择设备有有效候选配置、基线仍可用时可提交。页面维持现有技术/专家入口，领导端只接收有证据的摘要。

## 候选与检查语义

变更草稿提供两种输入：**逐台编辑完整候选配置**，或提交配置脚本。两者都必须在推演前得到可查看、可校验的完整候选配置与基线差异；`undo` / 删除在差异中可见。脚本解释必须按厂商及命令子集登记能力，不支持的命令应逐条报错并阻止候选发布，绝不把原始脚本直接拼进配置文件或宣称已执行。脚本是输入与审计证据，转换后的完整配置才送入 SDK。多设备草稿发布后，worker 从固定基线和所有候选配置构建新快照，成功初始化后自动建立 baseline → candidate 的 comparison；失败保留错误与输入，不产生“可推演”的假快照。本批只覆盖 Web 仿真，不下发真实设备；若后续需要下发，单独制定安全与回滚规格。

Underlay 分别检查模型 BGP/OSPF/ISIS 邻接变化和真实会话观测（若有输入）；链路两端速率、双工、MTU、VLAN、自协商、L2/L3 工作模式、IP 子网按明确的成对规则检查，分别给 `pass/fail/unknown/not_applicable` 和原始证据。环路用 `detectLoops` 示例流；黑洞、不可达和 IP 冲突按限定范围寻找证据，不把未覆盖全网写为“无黑洞/无冲突”。昂贵查询做限额、截断和失败隔离。

把现有业务关注项升为版本化意图：源/目的 IP 或规范网段、协议/端口、期望可达/隔离、可选必经/避开节点及策略版本。每次检查绑定固定意图版本与两快照。差异可达性报告“连通性是否变化”；路径变化使用固定且有限的代表流分别在两快照做 traceroute，比较规范化节点/接口路径集合，报告样本覆盖与多路径/截断，不能推论整个网段所有流路径不变。隔离检查在显式范围内搜索成功流见证；无见证仍须标示范围、模型覆盖和限制。汇报保存结果引用与输入版本，旧汇报不随资产/意图更新。

参考资料：用户提供《华为自动驾驶中网络仿真和自动配置调研》（2025-01-15，尤其第 2–12 页）。其“设备/链路变更 → 配置差异 → Underlay → Overlay/业务路径”的呈现顺序及链路配对指标可借鉴；流量预测、设备自动下发、VXLAN 专项、实时采集结果校真不在本批。Batfish 的 [补充数据格式](https://batfish.readthedocs.io/en/latest/formats.html)、[转发问题](https://batfish.readthedocs.io/en/latest/notebooks/forwarding.html)、[差异问题](https://batfish.readthedocs.io/en/latest/notebooks/differentialQuestions.html)用于能力边界；本仓库固定引擎/SDK 的真实兼容性仍由逐篇集成测试确定。

## 阶段门槛与风险

一期以“重复/断点分段推送、原子发布、双快照切换、拓扑/配置证据、人工维护和失败恢复”验收；二期以“多设备候选、模型/观测区别、未知字段、连通性与路径分报、隔离见证、固定版本结果”验收。两期都使用现有隔离 PostgreSQL、Batfish、API、worker、r1/r2 和 Cisco 四设备合成配置及浏览器；另生成带 Layer-1 和 `node.json` 的合成包。功能测试不证明现场转发精度或生产容量。

当前身份契约依据用户确认采用稳定 hostname、可变化管理 IP；Web 为其分配内部 UUID，改名不自动合并历史。配置脚本按现阶段范围只用于 Web 仿真，首批仅承诺经过真实 SDK 验证的 Cisco IOS 命令子集；若以后要下发真实设备，应另立安全和回滚规格。
