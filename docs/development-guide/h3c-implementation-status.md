# H3C 第一阶段实现记录

本文件跟踪已确认的 CR16000 / Comware 7 适配计划。原始需求及范围以本次用户确认的实施计划为准。

## 任务

1. 格式识别、终端文本归一化、解析任务接入。
2. statement tree 与接口、VPN、static、ISIS、BGP、策略、EVPN 厂商模型。
3. IPv4 接口/static/ISIS/BGP/策略转换及保守能力告警。
4. 原始 R1、Huawei 反例、合成配置及数据面测试。
5. 模块文档、支持矩阵、完整验证与代码审查。

## 实施记录

- 工作分支：`codex/h3c-comware`。保留已有文档和配置，不替换用户内容。
- 构建环境：已发现 Bazelisk 1.29.0，仓库指定 Bazel 9.2.0；首次测试需准备依赖。
- 接口核对：normalizer 必须保留缩进和原始行号；extractor 产出厂商对象；conversion 只消费厂商对象，不重新解析原始文本。
- 接口核对：所有无法由现有 VI 表达的数据保留在厂商对象中，并汇总告警；不新增 VI schema。
- 安全约束：原文配置按用户明确要求保留；测试不输出认证材料。
- 状态：第一阶段实现、代码审查修复、文档和全仓验证完成，已分批提交并合并；公开发布前按所有者新要求忽略私有 R1/R2，并从待推送历史移除其原文。
- Ruling: R1 验收计数改为 195 个接口、26 个 route-policy 节点。原计划的 185/24 是直接逐行匹配时遗漏分页符后语句导致；独立 Perl/awk 去分页统计确认 195/26。代价：旧计数不再作为验收基准，实际配置原文没有修改。
- 已验证：新增检测测试先失败（识别为 Cisco），新增 H3C 检测后 23 个格式检测用例通过；GB18030 和已有编码测试通过。
- 已验证：合成双节点 ISIS IPv4 路由（管理距离 15）、VRF eBGP/iBGP、direct/static 重分发、MED/社区策略行为通过。
- 已验证：原始 R1 经生产加载链路为 PASSED；无未识别目标命令；六类转换限制告警白名单通过；Huawei 反例通过。
- 已验证：跨 VRF 静态路由进入 RIB；connected、NULL0、显式 preference 测试通过；未创建 EVPN AF 或 VNI。
- 审查闭环：修复 whole-match 意外放行、Bridge-Aggregation 模式/成员解析、列表显式索引顺序、数字 advanced 列表识别；新增接口/BGP 参数校验、残缺 if-match 保守拒绝、SOO/RT 区分及 IPv6-only ISIS 告警回归。
- 兼容性：仅新 H3C 枚举成员使用 JSON 值 `h3c_comware`，保留其他 ConfigurationFormat 的既有 JSON 值；设备模型不推断具体硬件。
- 2026-09-23 验证：`bazel test //projects/batfish/... --test_output=errors --noshow_progress --jobs=6`，178/178 测试目标通过（包含 H3C 28 个 JUnit 用例及 grammar/representation/test PMD）。
- 环境记录：Bazel 下载格式化依赖返回 403，临时 downloader rewrite 也未成功；最终使用 curl 从官方 `repo.maven.apache.org` 下载相同制品到临时 `distdir`，由 Bazel 校验锁定 SHA 后成功执行 `//tools/format:format.fix`。未修改仓库依赖或锁文件。
- 最终验证（2026-09-23）：`bazel test //... --distdir=/private/tmp/h3c-bazel.l0kCKY --test_output=errors --noshow_progress --jobs=6` 成功，380/380 测试目标通过（247 个实际执行，133 个使用有效缓存），共分析 997 个目标。没有排除非测试目标或使用 `--build_tests_only`。
- 格式化后的 H3C 套件：28/28 JUnit 用例通过；grammar、representation、tests 的 PMD 通过；`//tools/format:format.check` 及 `git diff --check` 通过。
- 文档校验：development-guide 全部 Markdown 本地文件链接均存在。
- 环境补齐：全仓首次运行继续暴露未缓存依赖；按原有三个 Maven 锁文件补齐剩余 63 个制品，并逐个验证 SHA256。临时 distdir 仅用于本机引导，普通环境可直接运行文档中的 `bazel test //...`。
