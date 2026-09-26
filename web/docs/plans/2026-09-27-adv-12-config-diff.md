# ADV-12 配置文件差异实施计划

> 逐项按 `spec-dev`、TDD 和累计 runner 门槛执行；单篇全部通过才提交并进入 ADV-13。

**目标：** 以 ADV-11 的固定基线/候选比较记录创建配置差异任务，按原始文件路径分类并在受控限额内提供逐行变更块。

**架构：** changes 模块的 ConfigDiffService 从 ChangesService 取得冻结上下文，经 SnapshotsService 的文件接口读取受控内容，使用纯 Python 差异算法。composition 将 `analysis` 类型的 `config-diff` 操作分派至该 service；ResultsService 发布 kind=diff 的不可变结果并提供文件列表/详情。无 SDK 问题调用；worker、幂等、缓存、权限、上下文版本复核沿用既有机制。

**技术：** FastAPI、Pydantic、difflib、Pytest、PostgreSQL、真实 Batfish 测试快照、OpenAPI 类型生成。

**规格：** [ADV-12](../changeloge/advance/adv-12-configuration-diff.md)、[API 契约](../api-contracts.md)。基线提交 `cf52837b72`。

## 共同约束

- 基线和候选必须由 ADV-11 comparison 固定；candidate 是结果 context.snapshot，baseline 是 context.reference_snapshot。
- 使用 `SnapshotsService.files/read_file`，不直接访问 uploads repository、磁盘原始目录或 SDK 内部存储。
- 文件分类依据完整相对路径与原始 SHA-256；不猜测 rename。文本展示可标准化行结束，但原始摘要始终不变。
- 文件大小、行数、差异块数量和结果字节数有上限；摘要必须暴露“仅部分详情”及原因。
- 不增加未登记的专家 SDK 能力，不推断配置变化等于转发行为变化。

## 审查重点

- 原始字节不同但展示行相同：仍是 changed，并解释行结束/编码等可能原因。
- 二进制或不可解码文件：保留摘要、编码状态，不展示伪造文本。
- 删除或修改比较记录、快照状态在提交后变化：worker 拒绝过期上下文，旧结果仍可读取。
- 大文件、多文件、超长行、最大结果字节：给出可见截断原因，不越界读写。
- 身份/CSRF、幂等、缓存键和重试必须与现有任务行为一致。

## 步骤

- [x] 写失败测试：两个真实快照中的新增、删除、修改、相同文件及基线/候选方向；`kind=diff` 任务完成后分页文件列表与详情行号。
- [x] 写失败测试：UTF-8/GB18030、CRLF 与不可解码字节；只改变原始字节但文本行相同、文件大小/行数限额和超长行。
- [x] 增加配置差异纯算法与 DTO；通过 SnapshotsService 分页读文件，按路径比较 SHA，生成 bounded hunks 与明确警告。
- [x] 接入 ConfigDiffService 的提交、执行、缓存、发布/重试和 composition 分派，增加 POST 比较分析接口。
- [x] ResultsService 增加 kind=diff 发布、摘要与文件列表/详情 API；保持原子结果文件发布和基线/候选来源。
- [x] 生成前端 OpenAPI 类型；跑定向及累计后端/前端/浏览器/HTTPS 恢复门槛，审查边界，回写 spec、索引、证据并单独提交。
