# 运行与部署设计

本文定义目标部署行为。MVP-02提供API骨架、MVP-09接入独立worker，安装/启动/测试见 [后端 README](../backend/README.md)；完整团队部署和镜像仍属后续规格。

MVP-01 已验证 SDK 基线：Python 3.12.12、Pybatfish 2026.9.17.3748、引擎 revision `7d0deeeac4a09973b3876327f6aef721ee12f955`。JAR 摘要、隔离引擎启动及复现命令见 [兼容性报告](sdk-compatibility.md)。MVP-02 已生成 `backend/uv.lock` 并使用该锁文件复验真实 SDK 基线；文档/引擎字符串 0.36.0 不能用作 PyPI 安装版本。

## 部署单元

同一内网入口通过反向代理提供前端静态资源和 `/api/v1`，HTTPS 用于团队部署。API 和 worker 使用相同应用包、分开启动，共享 PostgreSQL 与受控文件卷。Batfish 的 9996 端口只向接入服务开放；浏览器不获得 SDK API key。PostgreSQL 不暴露给普通用户网络。

现有 Java 工程继续用 Bazel 构建。连接包含本分支 H3C/Huawei 改动的 Batfish 构建，记录 git revision、JAR/镜像摘要和 SDK 版本；不能以官方 latest 镜像替代而假定支持相同。加载 stable 和所需 experimental 模板，并通过能力探测判断是否可用。

首版单 worker，SDK 执行槽位为 1；不宣称多 worker 水平扩展。API 可处理并发元数据请求；worker 的数据库领取和引擎占用仍要有排他约束，避免误启动第二进程重复工作。

## 配置项与设计默认值

| 配置 | 默认/约束 |
| --- | --- |
| DATABASE_URL | 持久化接入后必填，应用专用 PostgreSQL 数据库；MVP-02 骨架可空且不连接数据库；不写入 Git |
| BATFISH_HOST / BATFISH_PORT | 服务端配置；默认端口 9996；用户参数不能覆盖 |
| BATFISH_API_KEY / BATFISH_TLS | 由部署环境提供；不回传浏览器 |
| READINESS_MAX_AGE_SECONDS | 60 秒；依赖状态过期或时间在未来均不 ready |
| DATA_DIR | 专用持久卷，不放代码库或前端静态目录 |
| SDK_CONCURRENCY | 首版固定 1 |
| MAX_QUEUED_JOBS_PER_USER / GLOBAL | 10 / 100；超限 429，避免队列无限增长 |
| UPLOAD_MAX_BYTES | 100 MiB；以实际接收字节计数 |
| UPLOAD_MAX_EXPANDED_BYTES / FILES | 500 MiB / 5000 个条目 |
| RESULT_MAX_BYTES / TABLE_ROWS | 100 MiB / 100000 行持久化输出上限 |
| SDK_REQUEST_TIMEOUT | Web 设计初始 120 秒，须显式传入；MVP-01 确认 SDK 默认 30 秒，单次请求超时且 GET 可重试，不是引擎运行时限 |
| JOB_WAIT_BUDGET | 初始 30 分钟；到期若不能证明引擎停止则进入未知占用 |
| SESSION_TTL | 8 小时绝对过期 |
| LOGIN_RATE_LIMIT | 同账号/IP 组合 5 次失败/分钟，短暂退避；不永久锁死账号 |
| UPLOAD_TTL / TEMP_TTL | 未消费上传与孤立临时文件 24 小时 |
| RESULTS_RETENTION | 默认不自动删除，管理员按需清理；容量告警而非静默丢历史 |

这些值是可调整的设计起点，不是完成的压测结果。SDK 可能在返回前构造完整对象，Web 输出截断无法保证引擎或 SDK 内存上限；用参数过滤、串行执行和容器/JVM 内存预算共同约束。对超大结果明确失败或标记截断，不能伪造完整计数。

## 文件与数据处理

支持多个配置文件或一个 Batfish 快照 ZIP。原始字节保留；可校验 UTF-8/GB18030 可解码性但不重写源文件。ZIP 仅接受一个可识别的快照根目录，必须有 configs；缺少/多个根目录报错。普通多文件上传包装为 configs，文件名冲突明确拒绝。

拒绝路径穿越、绝对路径、符号链接、加密压缩包、嵌套压缩包及超限解压。逐条目限额，不相信 ZIP 头声明的大小。文件操作限制在 upload_id 专属目录，不接受客户端服务器路径。保留可选 Batfish 输入目录但不执行任何内容。原始配置含敏感值，仅已登录团队成员可查看，不能进入普通访问日志和错误详情。

数据库/结果/上传卷与 Batfish 数据分别备份，并保存版本清单。恢复需在暂停任务领取时同时核对资源映射和引擎快照，不能仅恢复应用数据库就标记 ready。存储空间不足时新上传/结果发布明确失败，不损坏已有文件。

## 身份初始化

提供仅在无管理员时可用的一次性初始化命令，用户名和密码通过受保护输入传入，不提供固定默认密码。团队首次使用先创建管理员，再由管理员创建成员。初始化、用户停用、角色变更、密码重置、删除、未知占用解除写入审计事件。

账号停用在每次请求及任务实际执行前生效。已运行计算不假装被停止；结果保留发起人历史。管理员重置密码后旧 Cookie 失效，临时密码必须改为新密码。

## 任务对账和运维

live 只报告进程；ready 检查数据库、worker 最近心跳和引擎最近健康检查。空闲时定期做轻量版本/能力检查，不通过创建快照作为心跳。

当前健康路由带 `/api/v1` 前缀。MVP-09的ready读取真实数据库及worker/引擎最近观测，全部新鲜健康才返回200；缺失/过期/unknown返回503 NOT_READY。健康请求不调用SDK，空闲worker通过controller探测并记录观测，不能通过固定健康状态让部署误判可用。

worker失联或SDK超时后，不自动重放初始化/删除。相关任务置interrupted、引擎置unknown。管理员先停止旧worker，再检查Batfish诊断、必要时受控重启并确认空闲；对账接口同事务取得worker和SDK锁、记录依据和审计后解除阻塞，再重启worker。界面说明“停止等待不等于引擎停止”。公开SDK观测不能证明完成时保持未知，不猜测。

日志字段为 request_id、job_id、actor_id、resource_id、kind、duration、error_code；不记录明文密码、token、SDK key、完整配置、全量原始结果。服务端堆栈仅记录到受控日志，不回传用户。

MVP-02 未接入受控堆栈存储，未处理异常仅记录 request_id 和异常类型，不输出异常文本/输入/堆栈；HTTP 500 使用固定文案。请求 ID 由服务端生成，并写入响应头与错误信封。

MVP-01 实测后台分析可取得 work ID，并在新 Session 中查询状态/读取命名答案；`list_snapshots(verbose=True)` 可读取初始化状态。初始化公开方法仍同步，`get_snapshot()` 仅返回会话选中名称，不是执行完成证明。这些观测不覆盖 worker 崩溃窗口和引擎重启持久性，当前 unknown/管理员对账流程保持不变。SDK HTTP 重试可能使等待超过单次 timeout，不能将 SDK_REQUEST_TIMEOUT 直接当作 JOB_WAIT_BUDGET。

## 升级与回退

先暂停领取并等待在途任务收敛，备份数据库与数据卷，再应用迁移和固定版本包，运行兼容性烟测后恢复。失败时依据迁移是否可逆选择恢复备份，不承诺所有数据库迁移自动回滚。保留旧镜像/JAR 和版本清单，跨版本结果保留来源，不复用不兼容缓存。

MVP-15 分析查询使用公开后台工作句柄，在单个独占Session内观察终态后读取答案。普通参数被明确拒绝或工作已确定终止失败时允许后续任务；丢失提交响应、非终态超时等仍保留unknown。traceroute缺少可推导源地址不会使用管理地址替代；用户可补充source_ip提交新任务。失败答案仅在内存中提取固定提示，不将堆栈保存为用户结果。

## MVP-23 删除失败恢复

删除任务排队后不可取消，也不直接重试。失败/中断时资源保留deleting，检查任务详情中的固定网络/快照编号。若引擎状态unknown，先停止旧worker并核验实际引擎已空闲（必要时受控重启），按已有 `/admin/engine/reconcile` 流程记录依据解除引擎围栏；不能仅凭对象存在性判断引擎空闲。然后由管理员在删除任务页填写说明执行“检查远端并对账”，或POST `/api/v1/admin/deletions/{job_id}/reconcile`。服务端检查固定名称，存在则恢复删除前状态，不存在则补记deleted，未知则继续阻塞。已成功标deleted但输入清理失败时，同一对账入口可继续清理；共享输入仍被其他快照引用时不删除。历史任务状态、来源和结果保留，需再次删除时从资源列表重新确认。
