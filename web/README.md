# Batfish Web

团队共享的配置分析工作台，支持账号、配置上传与不可变快照、解析诊断、设备/接口、路由与最长前缀、虚拟 traceroute、历史结果导出及管理员删除。默认表单提供必要参数，专家参数折叠展示；结果按摘要、证据、原始信息逐层展开。

开发入口：[文档](docs/README.md)、[本机测试环境](docs/test-lab.md)、[后端](backend/README.md)、[前端](frontend/README.md)。下述部署使用当前分支已验证 JAR，不替换成官方 latest。

## 本机全新部署

要求 Docker Engine/Compose v2+（本轮实际5.0.2）、Python3.12、本仓库已构建 JAR，以及构建时可访问固定镜像、PyPI/npm。先在backend执行 `uv sync --locked`；从仓库根执行以下命令。状态目录必须全新，存放密码、证书和引擎构建输入，默认位于Git忽略的`.runtime`。

```bash
web/backend/.venv/bin/python web/scripts/deploy.py prepare --state web/.runtime/team-local
web/backend/.venv/bin/python web/scripts/deploy.py build --state web/.runtime/team-local
web/backend/.venv/bin/python web/scripts/deploy.py start --state web/.runtime/team-local
web/backend/.venv/bin/python web/scripts/deploy.py bootstrap --state web/.runtime/team-local
```

打开 `https://localhost:18443`。prepare产生仅供本机测试的30天自签证书，浏览器需信任该证书；首次管理员密码由终端隐藏输入，首次登录强制改密。没有默认管理员密码；重复bootstrap会拒绝。管理员创建普通成员后，成员可上传两套样例配置：`web/backend/tests/fixtures/small_network/configs`与`cisco_four/configs`。文件上传后需显式提交初始化，任务完成后选择快照开展分析。

compose项目名随机生成且以bfw-开头；所有管理动作通过指定state定位本实例，不控制其他容器。API与worker分进程，应用代码只读；数据库、应用文件、引擎数据分别使用命名卷。只发布回环HTTPS端口；数据库5432、引擎9996、API8000不映射宿主机。worker不在崩溃后自动重启/重放，需检查未知占用并人工恢复。容器健康与`/api/v1/health/ready`用于观察依赖；ready检查失败不等于引擎停止。

## 团队入口配置

在启动前将state目录的`tls/cert.pem`和`key.pem`替换成内网域名有效证书及私钥，保留父目录0700；绑定文件需可被proxy的UID101读取（本机生成的key.pem为0444，宿主访问受0700父目录限制），不要直接替换成代理无法读取的0600文件。文件只读挂载给proxy。修改`app.env`中的`AUTH_ALLOWED_ORIGINS`为精确HTTPS Origin JSON数组，`AUTH_COOKIE_SECURE=true`保持开启。在`compose.env`按实际网络策略设置`BFW_BIND`与`BFW_PORT`，只开放代理端口。更换Origin也需同步`deployment.json`的origin/port记录；不要修改project/state_dir/release身份。没有自动公网或生产发布步骤。

默认代理移除转发IP头，API禁用proxy headers，防止客户端伪造限流身份；同用户名通过代理共享失败限流窗口。此版不支持外部路径前缀；入口根路径与`/api/v1`同域。代理关闭访问日志，上传体限101MiB（包含multipart开销），应用仍按100MiB及解压限制校验。需要更大上传时必须同时调整代理与应用限制并重新验收。

`app.env`存数据库连接，`db-password`供PostgreSQL读取；两者为0600，不打印或提交。引擎模板与JAR只在服务端镜像内。应用依赖按uv.lock/pnpm-lock.yaml固定，基础镜像固定digest；prepare核对JAR SHA256并保存模板摘要至engine/provenance.json。Python容器3.12.13/Java25与宿主测试环境分别记录，以实际部署验收为准。

## 停止与恢复运行

```bash
web/backend/.venv/bin/python web/scripts/deploy.py stop --state web/.runtime/team-local
web/backend/.venv/bin/python web/scripts/deploy.py start --state web/.runtime/team-local
```

stop保留全部卷。不要用`down -v`做日常停止。停止给在途worker最多120秒退出，超时强制终止后仍须按未知占用流程恢复；停止容器不等于任务取消。

## 一致备份与恢复到新实例

先在工作台等待所有任务完成（取消不需要的排队任务），确认引擎idle。备份命令停止入口/API/worker，拒绝queued/running或非idle引擎，随后停止引擎；保存数据库dump、应用文件、引擎数据、配置、证书、镜像身份和校验摘要，最后停止数据库。失败时保持维护状态，不自动重新放行。文件均在0700私有备份目录内。

```bash
web/backend/.venv/bin/python web/scripts/deploy.py backup --state web/.runtime/team-local --backup web/.runtime/backup-001
web/backend/.venv/bin/python web/scripts/deploy.py restore --state web/.runtime/team-restored --backup web/.runtime/backup-001 --port 18444
```

restore只允许全新state/随机新项目和空卷，不覆盖既有数据；要求本机保留完全一致的三个应用/引擎镜像ID。它核验摘要，恢复数据库与两个文件卷，再迁移/启动并保留原账号、任务和结果。恢复后登录检查ready、原结果和原快照的新查询；原实例保持停止，避免误认为两个数据库可同时管理同一个引擎。

异机灾备还需安全保存三个镜像：从备份`deployment.json`读取release，对`bfw-backend:<release>`、`bfw-frontend:<release>`、`bfw-engine:<release>`执行Docker标准`image save`，在目标主机`image load`；同时保留固定Postgres镜像与当前源码。备份包含密码、私钥及原配置，按敏感数据保管。此版本不提供在线增量备份、跨版本自动回滚或高可用。

## worker失联或未知引擎

遵循[运行手册](docs/operations.md#任务对账和运维)：先停止本实例worker，检查日志与任务；无法确认空闲时受控重启本实例engine并等健康。使用管理员登录后的Cookie、Origin与CSRF调用`GET /api/v1/admin/engine`，再`POST /api/v1/admin/engine/reconcile`提交`resolution: restarted`及处理依据note。对账拒绝活跃worker/SDK，不自动重放interrupted任务；启动worker后按业务入口重试，初始化产生新快照。删除任务另按固定资源对账处理。

从state的compose.env与deployment.json取得对应项目，运维命令格式：

```bash
docker compose --env-file <state>/compose.env -p <deployment.json中的project> -f web/deploy/compose.yaml stop worker
# 已停止旧worker并确认本实例后：restart engine；待healthy再执行管理员对账；最后start worker。
```

## 验证

`verify_deployment.py`仅用于全新、独占的测试部署，会创建样例、强制终止本次worker、备份并恢复到新项目。不要对团队实例运行。

```bash
web/backend/.venv/bin/python web/scripts/verify_deployment.py --state web/.runtime/fresh-verification
```

先用prepare/build生成该全新state。实际结果与版本见[部署验收](docs/deployment-validation.md)。仅覆盖r1/r2两台和Cisco四台合成配置，不证明真实设备转发一致性或100设备容量。
