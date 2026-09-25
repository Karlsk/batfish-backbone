# MVP 累计验收矩阵

每轮运行 MVP-01～当前篇的必需检查；同一完整测试命令可以覆盖多行，但计数不重复累加。新增能力在所属篇实现时补充行为和实际命令，future 不等于通过。

| spec | 验收行为 | 命令及 cwd / 页面步骤 | 必需环境 | 拓扑 | 本轮结果 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| MVP-01 | SDK 版本/模板/网络/快照/诊断/查询/隔离/后台答案 | 仓库根：`web/backend/.venv/bin/python web/scripts/lab.py verify` 中 `test_sdk_baseline.py` | 固定 JAR、Pybatfish、隔离引擎 | r1/r2 及基线派生配置 | 通过（全套 189 passed） | [本轮累计](evidence/mvp-09-verification.json) |
| MVP-02 | live/ready、错误脱敏、请求 ID、DTO 不可变、导入约束 | 上述 verify 中 `test_foundation.py`、`test_architecture.py` | Python 锁定环境 | 无 | 通过（全套 189 passed） | [本轮累计](evidence/mvp-09-verification.json) |
| MVP-01/02 测试环境 | 配置打包/摘要/排他锁、真实服务健康、两个快照查询和交错隔离 | 上述 verify 中 `test_lab_inputs.py`、`test_lab_topologies.py`；单独 `lab.py smoke` 可用于诊断 | 真实 API、PostgreSQL、Batfish | r1/r2 + Cisco 四设备 | 通过（全套 189 passed） | [本轮累计](evidence/mvp-09-verification.json) |
| 通用 | Ruff、锁文件、文档链接、Git 空白检查 | backend：`.venv/bin/ruff check app tests migrations ../scripts/lab.py`、`uv lock --check`；仓库：`git diff --check` 和本地链接校验 | 当前源码及锁文件 | 无 | 通过 | [本轮累计](evidence/mvp-09-verification.json) |
| MVP-03 | 空库迁移、唯一/外键约束、事务回滚、受控存储及原子发布 | verify 中 `tests/test_persistence.py`（4项）、`tests/test_storage.py`（14项） | 隔离 PostgreSQL、临时文件卷 | 两套配置保留累计检查 | 通过（全套 189 passed） | [本轮累计](evidence/mvp-09-verification.json) |
| MVP-04 | 登录/改密/过期/Origin/CSRF/限流/撤销、并发初始化及脱敏审计 | verify 中 test_auth.py（11项）及真实 HTTP smoke（1项） | PostgreSQL、真实 API | 两套配置保留累计检查 | 通过（全套 189 passed） | [本轮累计](evidence/mvp-09-verification.json) |
| MVP-05 | 成员权限/分页/重名/停用重置/角色/并发最后管理员/审计原子性 | verify 中 test_users.py（8项）及真实 HTTP 管理 smoke（1项） | PostgreSQL、真实 API | 两套配置保留累计检查 | 通过（全套 189 passed） | [本轮累计](evidence/mvp-09-verification.json) |
| MVP-06 | 共享网络/身份/幂等恢复/独占/未知占用/真实 HTTP | verify 中 test_networks.py（10项）及真实 HTTP smoke（1项） | PostgreSQL、API、真实 Batfish | 两套配置累计检查 | 通过（全套 189 passed） | [本轮累计](evidence/mvp-09-verification.json) |
| MVP-07 | 实际字节/ZIP安全/编码摘要/所有权/并发消费/清理/提交故障 | verify 中 test_upload_archives.py（21项）、test_multipart.py（2项）、test_uploads.py（9项）及真实HTTP上传（2项） | PostgreSQL、API、私有文件卷 | r1/r2多文件 + Cisco ZIP | 通过（全套189 passed，smoke8 passed） | [本轮累计](evidence/mvp-09-verification.json) |
| MVP-08 | 幂等及并发/冻结上下文/限额/取消竞态/共享历史/身份 | verify中test_jobs.py（9项）、test_job_contracts.py（1项）及真实HTTP任务smoke（1项） | PostgreSQL、API；本篇无worker | 两套配置累计 | 通过（全套189 passed，smoke9 passed） | [本轮累计](evidence/mvp-09-verification.json) |
| MVP-09 | 独立worker/原子领取/身份/重试/预算与失联/unknown栅栏/管理员对账 | verify中test_worker.py（17项）及真实worker HTTP生命周期smoke（1项） | PostgreSQL、API、独立worker、真实SDK | 两套配置累计 | 通过（全套189 passed，smoke10 passed） | [本轮累计](evidence/mvp-09-verification.json) |
| MVP-10～15 | 各篇身份/资源/任务/分析行为及已有功能回归 | 从原 spec 逐篇登记实际测试，不预设不存在的命令 | API、PostgreSQL、worker、Batfish | 两套配置 | future | 未运行 |
| MVP-16～23 | 前端逻辑/类型/构建、浏览器操作、导出和删除互斥 | 从实际 package.json 与 spec 登记；不能仅用 lab.py verify | 已实现完整服务及浏览器 | 两套配置 | future | 未运行 |
| MVP-24/25 | 全新部署/恢复、双用户闭环与实际规模记录 | 按 spec 运行本机隔离部署及 Playwright | 完整服务及独立浏览器身份 | 两套配置 | future | 未运行 |

当真实应用 ready 接入健康生产者时更新环境级期望，同时保留缺依赖时不能假绿的测试。测试后的代码/配置/依赖变化使旧证据失效；文档回写单独补链接/格式检查。必需 skip、意外 deselected、失败或漏项都不允许提交。
