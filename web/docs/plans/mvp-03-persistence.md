# MVP-03 持久化与受控文件存储实施计划

> 按 superpowers:executing-plans 在当前批次串行实施；测试先行，每篇验收后一个提交。

**目标：** 实现可从空库升级的 PostgreSQL schema、明确的事务边界和内部 key 文件存储。依据：[MVP-03](../changeloge/mvp/mvp-03-persistence.md)。

**架构：** infrastructure 提供 SQLAlchemy engine/Base/事务和独立受控存储；各模块 models/repository 只在本模块内使用。composition 注册所有模型供 Alembic 获取 metadata，基础设施不反向导入业务模块。无新增业务 API/账号操作。

**技术：** Python 3.12、SQLAlchemy 2.0、psycopg 3、Alembic、实际 PostgreSQL 17.10。参考 [SQLAlchemy session](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)、[Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html)。版本在 uv.lock 固定。

## 顺序与验收

- [x] 写存储测试：内部 key 穿越/绝对路径/符号链接拒绝；临时内容不暴露；完整内容原子发布、拒绝覆盖、失败清理、受控删除。
- [x] 写真实数据库测试：隔离测试 schema，从空库升级；全部初始表/外键/唯一/状态约束；迁移 metadata 一致；失败事务无成功记录；数据库与文件联合失败。
- [x] 实现 infrastructure/database.py、storage.py 与明确的事务/文件发布使用协议；独立 Session，不建立通用 repository 框架。
- [x] 按模块建立 users/auth/networks/uploads/snapshots/jobs/results/audit 模型；幂等记录归 jobs 模块，最小 users/results repository；保留 UUID、JSONB、时区时间和软删除来源。
- [x] 生成固定初始 migration（不可从可变应用 metadata 动态创建 schema）；装配注册表；环境命令从隔离 lab 读取数据库连接，不打印凭证。
- [x] 累计回归 MVP-01～03（包括两套配置），刷新应用进程，独立审查，回写记录并提交。

## 重点边界

- 用户名、内部 engine 名称、会话 token_hash 与幂等作用域唯一；外键限制孤儿，软删除不移除历史引用。
- 文件 key 由服务端产生，限制单层安全字符标识；不接受客户端路径，不遍历 Batfish 卷。根目录私有，文件使用 dir_fd/O_NOFOLLOW，避免符号链接置换逃逸。
- 文件先暂存、fsync、原子发布，数据库标记成功只在发布后提交。事务回滚时无成功元数据；崩溃/提交结果未知可留下未引用文件，后续清理必须根据数据库引用决定，不假称跨文件系统/数据库分布式原子提交。
- 健康 live 仍可在依赖不可达时响应；数据库配置在创建持久化资源时必需。完整 ready 仍等待 worker/引擎状态源，不用数据库可连接伪造全部 ready。
- 不实现账号业务、队列调度或分析。跨模块通过 service 的长期规则继续由 AST 测试约束，models 只由本模块 repository 与 composition 直接导入。
