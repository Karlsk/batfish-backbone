# MVP 累计验收矩阵

下表记录MVP复验基线提交b59995435c；最新ADV-16及MVP累计回归见[ADV-16验收](evidence/adv-16-verification.md)（后端368、冒烟13、前端87、浏览器24通过）。

每轮运行 MVP-01～当前篇的必需检查；同一完整测试命令可以覆盖多行，但计数不重复累加。新增能力在所属篇实现时补充行为和实际命令，future 不等于通过。

| spec | 验收行为 | 命令及 cwd / 页面步骤 | 必需环境 | 拓扑 | 本轮结果 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| MVP-01 | SDK 版本/模板/网络/快照/诊断/查询/隔离/后台答案 | 仓库根：`web/backend/.venv/bin/python web/scripts/lab.py verify` 中 `test_sdk_baseline.py` | 固定 JAR、Pybatfish、隔离引擎 | r1/r2 及基线派生配置 | 通过（全套 289 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-02 | live/ready、错误脱敏、请求 ID、DTO 不可变、导入约束 | 上述 verify 中 `test_foundation.py`、`test_architecture.py` | Python 锁定环境 | 无 | 通过（全套 289 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-01/02 测试环境 | 配置打包/摘要/排他锁、真实服务健康、两个快照查询和交错隔离 | 上述 verify 中 `test_lab_inputs.py`、`test_lab_topologies.py`；单独 `lab.py smoke` 可用于诊断 | 真实 API、PostgreSQL、Batfish | r1/r2 + Cisco 四设备 | 通过（全套 289 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| 通用 | Ruff、锁文件、文档链接、Git 空白检查 | 仓库根：`web/backend/.venv/bin/ruff check web/backend web/scripts web/deploy`、`uv lock --check --project web/backend`、`git diff --check` 和本地链接校验 | 当前源码及锁文件 | 无 | 通过 | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-03 | 空库迁移、唯一/外键约束、事务回滚、受控存储及原子发布 | verify 中 `tests/test_persistence.py`、`tests/test_storage.py` | 隔离 PostgreSQL、临时文件卷 | 两套配置保留累计检查 | 通过（全套 289 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-04 | 登录/改密/过期/Origin/CSRF/限流/撤销、并发初始化及脱敏审计 | verify 中 test_auth.py及真实 HTTP smoke | PostgreSQL、真实 API | 两套配置保留累计检查 | 通过（全套 289 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-05 | 成员权限/分页/重名/停用重置/角色/并发最后管理员/审计原子性 | verify 中 test_users.py及真实 HTTP 管理 smoke | PostgreSQL、真实 API | 两套配置保留累计检查 | 通过（全套 289 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-06 | 共享网络/身份/幂等恢复/独占/未知占用/真实 HTTP | verify 中 test_networks.py及真实 HTTP smoke | PostgreSQL、API、真实 Batfish | 两套配置累计检查 | 通过（全套 289 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-07 | 实际字节/ZIP安全/编码摘要/所有权/并发消费/清理/提交故障 | verify 中 test_upload_archives.py、test_multipart.py、test_uploads.py及真实HTTP上传 | PostgreSQL、API、私有文件卷 | r1/r2多文件 + Cisco ZIP | 通过（全套289 passed，smoke12 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-08 | 幂等及并发/冻结上下文/限额/取消竞态/共享历史/身份 | verify中test_jobs.py、test_job_contracts.py及真实HTTP任务smoke | PostgreSQL、API；累计验证包含独立worker | 两套配置累计 | 通过（全套289 passed，smoke12 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-09 | 独立worker/原子领取/身份/重试/预算与失联/unknown栅栏/管理员对账 | verify中test_worker.py及真实worker HTTP生命周期smoke | PostgreSQL、API、独立worker、真实SDK | 两套配置累计 | 通过（全套289 passed，smoke12 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-10 | 原子消费/幂等/取消中断重试/不可变身份/质量门/options/失败保留输入 | verify中test_snapshots.py及独立worker快照HTTP smoke | PostgreSQL、API、独立worker、固定SDK | 两套ZIP + 合成解析警告 | 通过（全套289 passed，smoke12 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-11 | 四类诊断/源行/厂商限制/质量阻断/文件解码与分页边界 | verify中test_diagnostics.py及test_source_lines.py；真实两套ZIP的HTTP smoke核对诊断及全部源文件 | PostgreSQL、API、独立worker、固定SDK | 两套配置及合成未知命令 | 通过（全套289 passed，smoke12 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-12 | 能力开关/options/结构化结果/分页截断/缓存版本与身份/结果和job原子发布 | verify中test_results.py；真实两套SDK node/trace及HTTP结果smoke；分层新增4项 | PostgreSQL、API、worker、固定SDK | 两套配置 | 通过（全套289 passed，smoke12 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-13 | 字面/表达式选择、SDK设备接口对照、空结果、参数/身份、终态错误不冻结与未知保持占用 | verify中test_inventory.py；正式HTTP/CLI worker两套配置分析smoke | PostgreSQL、API、worker、固定SDK | 两套配置+特殊名称派生配置 | 通过（全套289 passed，smoke12 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-14 | IPv4/VRF/协议/匹配方式、SDK路由与LPM对照、下一跳结构与运行阶段 | verify中test_routing.py；四类已开放分析正式HTTP/CLI worker smoke | PostgreSQL、API、worker、固定SDK | 两套配置+Cisco多VRF派生 | 通过（全套289 passed，smoke12 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-15 | IPv4协议端口校验、SDK Flow/Trace一致、混合路径/截断、源地址诊断、模型限制 | verify中test_traceroute.py；五类分析及Flow/Trace正式HTTP/worker smoke | PostgreSQL、API、worker、固定SDK | 两套配置+ECMP拒绝/无源派生 | 通过（全套289 passed，smoke12 passed） | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-16 | 查询隔离/CSRF/渐进组件/常驻上下文/中文桌面布局 | frontend: pnpm test/check:api/typecheck/build/format:check/test:e2e | 实际API、Chromium及组件harness | 后端保留两套配置 | 前端47 passed；浏览器14×2 passed；后端289 passed/0skip | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-17 | 强制改密/退出清缓存/成员入口与403/管理员增改重置/双浏览器停用撤销 | frontend全部scripts及auth-users.spec.ts | 真实API、PostgreSQL、两个独立浏览器 | 两套配置保留 | 前端47/浏览器14×2/后端289通过；0skip | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-18 | 上传失败/稳定幂等/上下文与路由草稿保护/服务限额/真实双拓扑初始化 | frontend全scripts、networks-snapshots.spec.ts；backend全verify | 真实API/worker/PG/Batfish/浏览器 | r1/r2文件 + Cisco ZIP | 后端289/前端47/浏览器14×2，0skip | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-19 | 任务轮询/取消竞态/不可变重试/原始行诊断与缺位置 | frontend全部scripts、jobs与diagnostics单测及真实浏览器 | 完整隔离服务/Chromium | 两套配置 + worker受控暂停恢复 | 后端289/前端47/浏览器14×2，0skip | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-20 | 设备/接口/路由/LPM请求与真实候选、结果分页过滤/固定来源/下一跳/空结果 | frontend全scripts、routing/results单测、analysis.spec.ts | 完整隔离服务/Chromium | 两套配置 | 后端289/前端47/浏览器14×2，0skip | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-21 | 真实起点/接口、单向路径、多Flow、混合disposition、未知动作、ACL/截断 | frontend全scripts、traceroute.test.tsx/traceroute.spec.ts | 完整隔离服务/Chromium | 两套配置及Cisco合成ACL副本 | 后端289/前端47/浏览器14×2，0skip | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-22 | JSON完整保存数据/来源、CSV元数据/公式Unicode/路径拒绝、权限与真实下载 | tests/test_exports.py、ResultExport.test.tsx、真实浏览器下载内容比对 | 完整隔离服务/Chromium | 两套配置 | 后端289/前端47/浏览器14×2，0skip | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-23 | 删除/提交/创建重试互斥、固定对账、共享输入/参考保护、权限/来源保留 | tests/test_deletion.py、删除/对账前端单测、analysis browser删除helper | 完整隔离服务/Chromium | 两套配置 | 后端289/前端47/浏览器14×2，0skip | [本轮累计](evidence/mvp-recheck-2026-09-26.json) |
| MVP-24 | HTTPS全新部署、重启/unknown、三卷备份恢复/历史与新查询 | scripts/verify_deployment.py + playwright.deployment.config.ts | 独占Compose/HTTPS/Chromium | 两套配置 | 完整演练通过；部署浏览器3×2，0skip | [本轮](evidence/mvp-recheck-2026-09-26.json) |
| MVP-25 | 独立SDK五类对照、双用户配置/结果/身份隔离、实际规模采样 | integration/test_mvp_acceptance.py + playwright.acceptance.config.ts | 真实lab与恢复后HTTPS生产构建 | 两套配置、两个独立用户 | 后端289/前端47/浏览器14×2+3×2+1×2，0skip | [报告](mvp-acceptance.md) / [本轮](evidence/mvp-recheck-2026-09-26.json) |

当真实应用 ready 接入健康生产者时更新环境级期望，同时保留缺依赖时不能假绿的测试。测试后的代码/配置/依赖变化使旧证据失效；文档回写单独补链接/格式检查。必需 skip、意外 deselected、失败或漏项都不允许提交。

## ADV 连续批次累计范围

用户明确授权ADV-01～18连续实现与提交。每轮保留上表全部MVP验收，再加入已实现的ADV；ADV-10、ADV-18阶段验收不能由单元测试替代。

| spec | 验收行为 | 命令/环境 | 当前状态 |
| --- | --- | --- | --- |
| ADV-01 | 四视图SDK对照、节点/边/邻域/截断、缓存隔离、同Session/失败预算、真实HTTP worker | lab.py verify/smoke + 全部前端/浏览器/HTTPS部署恢复 | 本轮累计后端307/冒烟12/前端55/浏览器16/部署3×2/双用户1×2及全新恢复通过 |
| ADV-02 | 聚焦/一跳、四视图、接口和路由入口、固定来源、旧响应隔离/清理/重试、双主题与键盘入口 | topology.test.tsx、submission.test.tsx、topology.spec.ts及累计全部门槛 | [本轮全通过](evidence/adv-02-verification.md)：后端307、前端55、浏览器16、部署3×2、双用户1×2 |
| ADV-03 | 固定BGP两问题、AS错配/模型成功/IPv6限制、原始列和筛选、幂等/上下文/缓存 | test_bgp.py，lab.py verify/smoke，全部前端/浏览器/HTTPS恢复 | [本轮全通过](evidence/adv-03-verification.md)：后端314、冒烟12、前端55、浏览器16、部署3×2、双用户1×2 |
| ADV-04 | BGP双模式独立结果、状态精确筛选、未知远端/详情/路由入口、双主题及空结果 | bgp.test.tsx、bgp.spec.ts、lab.py verify/smoke、全部前端/浏览器/HTTPS恢复 | [本轮全通过](evidence/adv-04-verification.md)：后端314、冒烟12、前端58、浏览器18、部署3×2、双用户1×2 |
| ADV-05 | ACL放行/显式拒绝/隐式拒绝与SDK对照、过滤器解析、无匹配无结论、厂商模型拒绝、严格参数、真实API/worker | test_filters.py、lab.py verify/smoke、全部前端/浏览器/HTTPS恢复 | [本轮全通过](evidence/adv-05-verification.md)：后端318、冒烟12、前端58、浏览器18、部署3×2、双用户1×2 |
| ADV-06 | 设备/ACL候选、基础/高级参数、动作与证据分级、隐式拒绝、无匹配/厂商限制、路径预填、深浅主题 | filter-test.test.tsx、filter-result.test.tsx、acl.spec.ts、lab.py verify/smoke、全部前端/浏览器/HTTPS恢复 | [本轮全通过](evidence/adv-06-verification.md)：后端318、冒烟12、前端70、浏览器20、部署3×2、双用户1×2 |
| ADV-07 | 有界ACL/设备范围、固定搜索动作与headers、示例Flow可复核、遮蔽/空条件原因区分、无示例不推断安全、厂商模型拒绝 | test_filter_search.py、lab.py verify/smoke、全部前端/浏览器/HTTPS恢复 | [本轮全通过](evidence/adv-07-verification.md)：后端325、冒烟12、前端70、浏览器20、部署3×2、双用户1×2 |
| ADV-08 | 搜索/规则诊断独立草稿、能力目录默认与开关、示例Flow按原协议/IP/端口回测、阻挡/不可匹配证据分层、空或部分结果不推断安全 | acl-advanced.test.tsx、advanced-results.test.tsx、acl-advanced.spec.ts及累计全部门槛 | [本轮全通过](evidence/adv-08-verification.md)：后端325、冒烟12、前端78、浏览器21、部署3×2、双用户1×2 |
| ADV-09 | 登记能力唯一目录、完整参数schema、专用/专家查询结果等价、未知/禁用/任意SDK方法及上下文覆盖拒绝、JSON错误保留输入和字段路径 | test_expert_query.py、expert.test.tsx、expert.spec.ts及累计全部门槛 | [本轮全通过](evidence/adv-09-verification.md)：后端329、冒烟12、前端81、浏览器22、部署3×2、双用户1×2 |
| ADV-10 | 同一快照跨拓扑/BGP/ACL/专家，直接SDK边与会话对照，AS错配/孤立节点/permit与两类deny/遮蔽与空匹配，阶段1双用户不回退 | test_advance_phase2.py、advance-phase2.spec.ts及全部累计后端/前端/浏览器/HTTPS恢复门槛 | [第二阶段全通过](evidence/adv-10-verification.md)：后端330、冒烟12、前端81、浏览器23、部署3×2、双用户1×2 |
| ADV-11 | 固定基线/候选方向、同网络/状态/版本/覆盖、软删除权限、在途任务与快照删除竞态 | test_comparisons.py、迁移测试及全部累计后端/前端/浏览器/HTTPS恢复门槛 | [本轮全通过](evidence/adv-11-verification.md)：后端336、冒烟12、前端81、浏览器23、部署3×2、双用户1×2 |
| ADV-12 | 文件新增/删除/修改、原始字节摘要与编码/换行、行号/截断、对比方向、任务缓存和历史、真实worker API | test_config_diff.py、真实配置冒烟及全部累计后端/前端/浏览器/HTTPS恢复门槛 | [本轮全通过](evidence/adv-12-verification.md)：后端345、冒烟13、前端81、浏览器23、部署3×2、双用户1×2 |
| ADV-13 | 真实SDK增删/Changed方向、ECMP逐行与Unchanged过滤、范围内空结果、有类型参数、缓存/导出/历史、独立worker API | test_route_diff.py、真实配置冒烟及全部累计后端/前端/浏览器/HTTPS恢复门槛 | [本轮全通过](evidence/adv-13-verification.md)：后端351、冒烟13、前端81、浏览器23、部署3×2、双用户1×2 |
| ADV-14 | 真实SDK候选新增/消失可达、路径变化但可达性不变、条件空结果、截断不确定、无效起点、严格参数、缓存/导出/历史、独立worker API | test_reachability_diff.py、真实配置冒烟及全部累计后端/前端/浏览器/HTTPS恢复门槛 | [本轮全通过](evidence/adv-14-verification.md)：后端357、冒烟13、前端81、浏览器23、部署3×2、双用户1×2 |
| ADV-15 | 固定双快照方向与交换草稿、配置按文件读详情、路由新增/消失、限定 Flow 双侧路径、覆盖/截断/版本冲突/空结果、历史结果与快照状态读偏斜回归 | changes.test.tsx、changes.spec.ts、test_snapshots.py及MVP+ADV-01～15全部累计门槛 | [本轮全通过](evidence/adv-15-verification.md)：后端358、冒烟13、前端87、浏览器24、部署3×2、双用户1×2 |
| ADV-16 | 节点/接口精确校验、不可变派生、来源和初始化质量、幂等与引擎忙、SDK未确认/失败、基线引用删除保护与竞态 | test_fault_scenarios.py、迁移/分层、独立真实HTTP worker及MVP+ADV-01～16全部累计门槛 | [本轮全通过](evidence/adv-16-verification.md)：后端368、冒烟13、前端87、浏览器24、部署3×2、双用户1×2 |
