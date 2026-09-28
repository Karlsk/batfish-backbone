# CMDB/SIM 批次累计验证门槛

本文件仅在用户显式启动 `CMDB-...` 或 `SIM-...` 范围时使用。先读 `web/docs/cmdb-simulation-design.md`、目标/前置 spec、`web/docs/validation.md` 和 `web/docs/test-lab.md`；不得从文档状态推断功能已存在。

## 基线和矩阵

- 首篇开始前实跑当前 MVP/ADV/LDR 后端、前端、浏览器和隔离部署基线，记录源码身份、实际 collected/passed/failed/skipped 与环境版本。已有证据用于了解预期，不能代替本轮运行。
- 每篇在 `web/docs/validation-matrix.md` 增加当前及已完成 CMDB/SIM 行，明确 API、数据库、worker、SDK、UI、恢复与文档验收。未实现的未来项标 future；必需 skip、失败或没有环境都挡住提交。
- 每篇运行受影响目标测试、全量已实现后端/前端与浏览器流程，并复核此前 CMDB/SIM 验收行为；跨模块契约变更必须复验依赖方。CMDB-11 和 SIM-17 重新从空库、两种合成拓扑与生产构建前端做端到端阶段验收，包括 HTTPS 重启/恢复。

## 真实输入与事实语义

- 使用 `lab.py serve/seed/smoke/verify` 的隔离 PostgreSQL、Batfish、API/worker，以及 r1/r2 和 Cisco 四设备合成配置；另生成确定性的 `node.json` 与 `batfish/layer1_topology.json`，测试普通 ZIP、分段推送、重复包、断点续传、无物理拓扑旧包与历史切换。
- CMDB-05 起实际通过采集凭证的 HTTP 分段接口，而不是只直接调用 Python helper；CMDB-06 起检查原子晋升与 worker 恢复。CMDB-09 起用浏览器核查拓扑、主题、右键/键盘/触屏替代菜单和快照切换。
- SIM-04 起对完整配置及命令脚本分别核查生成的候选全文、差异、支持子集与拒绝行为；SIM-05 起与固定 SDK 原始结果对照。SIM-07～14 的模型/真实观测、未知、截断、可达性/路径变化和双向隔离必须分开断言，不能用空结果等同通过。
- 使用真实 SDK 的问题先核对固定版本兼容性；不因官网 latest 支持某能力就宣称本仓库引擎支持。引擎访问串行，任务超时/worker 失联按现有未知占用机制对账。
- 测试只证 Web 功能和合成配置下的固定模型行为，不证明现场设备转发、全部厂商命令或大规模容量。

## 提交与证据

记录每轮命令及 cwd、版本、输入包哈希、源码身份、结果计数、页面步骤和未覆盖范围。测试后改了已测代码/依赖/配置要重跑相关与累计门槛；只回写文档则检查链接、索引和 staged diff。证据必须脱敏，不把采集凭证、私有配置或本机 runtime 文件提交。CMDB-11 未通过不开始 SIM；任一篇有必需检查缺失则停在 verifying，不提交、不继续。
