# MVP 累计验收矩阵

每轮运行 MVP-01～当前篇的必需检查；同一完整测试命令可以覆盖多行，但计数不重复累加。新增能力在所属篇实现时补充行为和实际命令，future 不等于通过。

| spec | 验收行为 | 命令及 cwd / 页面步骤 | 必需环境 | 拓扑 | 本轮结果 | 证据 |
| --- | --- | --- | --- | --- | --- | --- |
| MVP-01 | SDK 版本/模板/网络/快照/诊断/查询/隔离/后台答案 | 仓库根：`web/backend/.venv/bin/python web/scripts/lab.py verify` 中 `test_sdk_baseline.py` | 固定 JAR、Pybatfish、隔离引擎 | r1/r2 及基线派生配置 | 通过（全套 87 passed） | [本轮累计](evidence/mvp-03-verification.json) |
| MVP-02 | live/ready、错误脱敏、请求 ID、DTO 不可变、导入约束 | 上述 verify 中 `test_foundation.py`、`test_architecture.py` | Python 锁定环境 | 无 | 通过（全套 87 passed） | [本轮累计](evidence/mvp-03-verification.json) |
| MVP-01/02 测试环境 | 配置打包/摘要/排他锁、真实服务健康、两个快照查询和交错隔离 | 上述 verify 中 `test_lab_inputs.py`、`test_lab_topologies.py`；单独 `lab.py smoke` 可用于诊断 | 真实 API、PostgreSQL、Batfish | r1/r2 + Cisco 四设备 | 通过（全套 87 passed） | [本轮累计](evidence/mvp-03-verification.json) |
| 通用 | Ruff、锁文件、文档链接、Git 空白检查 | backend：`.venv/bin/ruff check app tests migrations ../scripts/lab.py`、`uv lock --check`；仓库：`git diff --check` 和本地链接校验 | 当前源码及锁文件 | 无 | 通过 | [本轮累计](evidence/mvp-03-verification.json) |
| MVP-03 | 空库迁移、唯一/外键约束、事务回滚、受控存储及原子发布 | verify 中 `tests/test_persistence.py`（4项）、`tests/test_storage.py`（14项） | 隔离 PostgreSQL、临时文件卷 | 两套配置保留累计检查 | 通过（全套 87 passed） | [本轮累计](evidence/mvp-03-verification.json) |
| MVP-04～15 | 各篇身份/资源/任务/分析行为及已有功能回归 | 从原 spec 逐篇登记实际测试，不预设不存在的命令 | API、PostgreSQL、worker、Batfish | 两套配置 | future | 未运行 |
| MVP-16～23 | 前端逻辑/类型/构建、浏览器操作、导出和删除互斥 | 从实际 package.json 与 spec 登记；不能仅用 lab.py verify | 已实现完整服务及浏览器 | 两套配置 | future | 未运行 |
| MVP-24/25 | 全新部署/恢复、双用户闭环与实际规模记录 | 按 spec 运行本机隔离部署及 Playwright | 完整服务及独立浏览器身份 | 两套配置 | future | 未运行 |

当真实应用 ready 接入健康生产者时更新环境级期望，同时保留缺依赖时不能假绿的测试。测试后的代码/配置/依赖变化使旧证据失效；文档回写单独补链接/格式检查。必需 skip、意外 deselected、失败或漏项都不允许提交。
