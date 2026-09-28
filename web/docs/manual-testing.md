# Batfish Web 手动测试指南

适用范围：当前工作树的技术工作台、专家查询和领导视图。测试只验证 Web 流程、已保存结果与配置模型展示；不证明真实设备转发行为。请在**全新本机部署**执行，避免污染已有团队数据。每项记录日期、操作者、网络/快照名、任务或结果编号、实际现象与截图；若与预期不同，记录页面上的请求编号和任务中心状态，不把失败写成通过。

## 1. 测试物料与前提

从仓库根目录使用 [物料目录](manual-testing/materials/) 中的 ZIP，**无需真实设备**。ZIP 内均以 `configs/` 为顶层目录。

| 文件 | 用途 | 可核对的输入事实 |
| --- | --- | --- |
| [r1-r2.zip](manual-testing/materials/r1-r2.zip) | MVP 两设备 | r1、r2；r1 的 10.0.0.1/32 到 r2 的 10.0.0.2/32，链路 192.0.2.0/30 |
| [cisco-four-baseline.zip](manual-testing/materials/cisco-four-baseline.zip) | 四设备基线、拓扑/路由/路径 | c1/c2/c3/c4，OSPF 菱形；c1 → c4，目标 10.64.0.4 |
| [cisco-four-candidate-c2-link-down.zip](manual-testing/materials/cisco-four-candidate-c2-link-down.zip) | 变更候选 | 仅把 c2 的 GigabitEthernet0/1 从 `no shutdown` 改为 `shutdown`；其余文件与基线相同 |
| [example-live-bgp-acl.zip](manual-testing/materials/example-live-bgp-acl.zip) | BGP、ACL 与专家能力 | 本仓库 `networks/example/live/configs` 的 13 台合成设备；含 as2border1 的 BGP 与 `OUTSIDE_TO_INSIDE` ACL |

校验：在 `web/docs/manual-testing/materials` 运行 `shasum -a 256 -c SHA256SUMS`。四设备配置与地址表见 [原始物料说明](../backend/tests/fixtures/cisco_four/README.md)。这些配置来自仓库公开样例；本指南只断言输入和工作流，不预设每条模型路径一定成功。

准备 Docker Engine + Compose v2、Python 3.12、`uv`、Bazel 9.2.0 与 Java 25。完整 Docker 部署需要先在宿主机构建本仓库 Batfish JAR，再由 Compose 把它构建进引擎镜像；不需要另起一个宿主机 Java 引擎。预留本机 `18443` 端口；首次构建镜像需要可访问项目锁定的镜像及依赖源。

## 2. 构建 Batfish、Web 镜像并部署 HTTPS 环境

以下命令都在仓库根目录执行。`web/.runtime/manual-acceptance` 必须此前不存在；若只是停止过同名实例，应按 [Web README](../README.md) 重新启动，不要重新 `prepare`。

### 2.1 构建 Batfish 引擎输入

```bash
bazel build //projects/allinone:allinone_main_deploy.jar --jobs=6
shasum -a 256 bazel-bin/projects/allinone/allinone_main_deploy.jar
```

预期 JAR 摘要为 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`。这是当前 `web/scripts/deploy.py` 固定的已验收引擎版本；摘要不同就停止，先核对源码版本和 [SDK 兼容性报告](sdk-compatibility.md)，不要改用任意 latest 或跳过校验。

### 2.2 准备部署状态并 Docker build Web 项目

```bash
uv sync --locked --project web/backend
web/backend/.venv/bin/python web/scripts/deploy.py prepare --state web/.runtime/manual-acceptance
web/backend/.venv/bin/python web/scripts/deploy.py build --state web/.runtime/manual-acceptance
```

`prepare` 把已校验的 JAR 和问题模板复制到私有 state，生成数据库密码及本机自签证书；`build` 实际调用 `docker compose build`，从 `web/backend/Dockerfile`、`web/frontend/Dockerfile` 和 state 中的 `engine/Dockerfile` 构建 **API/worker、前端代理、Batfish 引擎**镜像。PostgreSQL 使用 Compose 中固定摘要的基础镜像。无需再单独运行 `docker build`，也不要手工给镜像取与 state 不一致的 tag。可以用 `docker image ls 'bfw-*'` 确认三类镜像已生成。

若要直接使用 Docker CLI，下面是与 `deploy.py build` 等价的镜像构建方式；**二选一执行**，不要重复构建：

```bash
BFW_MANUAL_PROJECT=$(python3 -c 'import json; from pathlib import Path; print(json.loads(Path("web/.runtime/manual-acceptance/deployment.json").read_text())["project"])')
docker compose --env-file web/.runtime/manual-acceptance/compose.env \
  -p "$BFW_MANUAL_PROJECT" -f web/deploy/compose.yaml build engine api proxy
```

这三个目标分别构建 Batfish 引擎、Web 后端和 Web 前端；worker、迁移容器复用后端镜像。项目名必须从本次 state 读取，不能自行起名。

### 2.3 Docker 部署 Web 项目并检查服务

```bash
web/backend/.venv/bin/python web/scripts/deploy.py start --state web/.runtime/manual-acceptance
curl -k -i https://localhost:18443/api/v1/health/live
curl -k -i https://localhost:18443/api/v1/health/ready
```

`start` 实际调用 `docker compose up -d --no-build --wait`，依次启动 PostgreSQL、迁移、Batfish 引擎、API、独立 worker 和 HTTPS 前端代理；只向宿主机 `127.0.0.1:18443` 发布代理端口。预期 `live` 和依赖就绪后的 `ready` 返回 HTTP 200。浏览器打开 <https://localhost:18443>，仅在这套本机测试环境接受 `prepare` 生成的自签证书。若 `ready` 仍为 503，先等待容器健康并查看本实例的 `api`、`worker`、`engine` 日志；不要通过隐藏“服务尚未就绪”继续验收。可先运行 `docker ps --filter name=bfw-` 定位本次容器，再用 `docker logs <容器名>` 查看日志。启动失败时保留终端输出、请求编号和本实例日志。完整运维说明见 [Web README](../README.md)。

若 2.2 使用的是直接 Docker CLI 构建，也可以用同一项目名直接部署（与 `deploy.py start` **二选一**）：

```bash
BFW_MANUAL_PROJECT=$(python3 -c 'import json; from pathlib import Path; print(json.loads(Path("web/.runtime/manual-acceptance/deployment.json").read_text())["project"])')
docker compose --env-file web/.runtime/manual-acceptance/compose.env \
  -p "$BFW_MANUAL_PROJECT" -f web/deploy/compose.yaml \
  up -d --no-build --wait --wait-timeout 300
docker compose --env-file web/.runtime/manual-acceptance/compose.env \
  -p "$BFW_MANUAL_PROJECT" -f web/deploy/compose.yaml ps
```

首次登录使用 `admin/admin`。页面必须要求立即修改为**至少 12 字符**的新密码；改密后使用新密码重新登录，旧的 `admin/admin` 必须失效。已有用户的数据库不会因为启动而重置密码。随后在“用户管理”创建普通成员 `manual-member`，设置符合页面要求的临时密码；在另一浏览器隐私窗口以该成员登录并按提示改密。不要把真实密码、Cookie 或证书私钥写入测试记录。

### 2.4 可选：用 Java 直接运行 Batfish

只做本机开发、不构建整套 Web 镜像时，可用 `web/scripts/lab.py` 管理独立实验环境。它会直接用 Java 25 运行上述 JAR，同时启动本机 FastAPI、worker 和临时 PostgreSQL；前端另用 Vite 启动。这条路径与 2.2～2.3 的 Compose 全栈部署**二选一**，不要让两套环境共用端口或数据库。

```bash
# 终端 A：保持运行；默认引擎 19996、API 18000、数据库 15439
uv sync --locked --project web/backend
web/backend/.venv/bin/python web/scripts/lab.py serve
```

```bash
# 终端 B：开发前端
cd web/frontend
pnpm install --frozen-lockfile
pnpm dev
```

访问 <http://127.0.0.1:15173>。此实验环境的测试管理员由 `lab.py` 创建，凭证在 Git 忽略的 `web/.runtime/test-lab/current.json` 所指运行目录的 `auth.json`，**不是**全新 Docker 部署的 `admin/admin`；细节见 [本机功能测试环境](test-lab.md)。本指南第 3～6 节的默认账号及 HTTPS 步骤以 2.1～2.3 的完整 Docker 部署为准。

## 3. 创建四份快照（专业工作台）

“专业模式”在产品中对应**技术工作台**；“专家模式”是技术工作台内的“专家查询”和各页折叠的高级选项，并非独立登录入口。登录后默认进入技术工作台；右上角可切换“领导视图”。

1. 打开“网络与快照” → “创建网络”，输入 `手测-双设备`，提交；状态变成“可用”后点“查看快照”。
2. 选择“ZIP压缩包” → “选择ZIP文件”，上传 `r1-r2.zip`；点“上传并校验”，确认显示 **2 个文件、尚未初始化**。输入快照名称 `r1-r2-基线`，保留默认高级选项，点“提交初始化”。在“任务中心”或快照列表等到状态“就绪”或“就绪但有警告”；若失败，打开“诊断”，记录原因。
3. 返回“网络与快照”，新建 `手测-Cisco四设备`。用相同方法依次上传 `cisco-four-baseline.zip` 与 `cisco-four-candidate-c2-link-down.zip`，分别命名 `cisco-基线`、`cisco-c2链路关闭`。**两份快照必须属于同一网络**，分别等待初始化完成，不覆盖基线。
4. 新建 `手测-BGP-ACL`，上传 `example-live-bgp-acl.zip`，命名 `example-live`，等待就绪。若部分配置产生解析警告，保留警告并在“诊断”查看具体文件和行，不把警告当作自动成功或失败。
5. 在右上方切换网络/快照，确认标题与所选内容一致；刷新页面并再次查看，历史结果仍标注创建时的网络和快照。普通成员窗口也应能看到共享网络，但看不到仅管理员可用的用户管理操作。

## 4. 专业工作台逐步测试

每次检查前先在顶部确认**网络、快照**。执行后到“任务中心”确认任务完成，再按“摘要 → 证据 → 详情/原始信息”查看结果。

| 步骤 | 操作 | 预期检查点 |
| --- | --- | --- |
| P1 配置质量 | 选 `手测-双设备 / r1-r2-基线`，从快照列表点“诊断”。 | 能看到解析状态、问题/限制；没有问题时也明确为空，不显示假造的健康分。 |
| P2 设备/接口 | 打开“网络分析”，依次运行设备和接口查询。 | 设备清单包含 r1、r2；接口结果绑定当前快照，可展开详情。 |
| P3 路由/LPM | 在“网络分析”运行路由查询，输入目标网段 `10.0.0.2/32`；再运行最长前缀查询，目的地址 `10.0.0.2`。 | 显示提交范围、任务状态和保存的路由证据；路由模型结论与空结果区别展示。 |
| P4 路径 | 在“网络分析”点“虚拟 traceroute”，起点设备 r1，目标 `10.0.0.2`，提交“推演路径”。 | 可查看路径/逐跳或明确的不可达、模型限制；页面说明这是单向虚拟推演。 |
| P5 拓扑 | 切到 `手测-Cisco四设备 / cisco-基线`，打开“网络拓扑”，默认三层关系运行；再选 OSPF 关系。 | 图、设备及关系列表可操作；聚焦 c1 的邻域并打开设备/接口证据。关系不标成实时物理链路。 |
| P6 变更 | 打开“变更对比”，基线选 `cisco-基线`，候选选 `cisco-c2链路关闭`，创建比较；依次运行“配置变化”“路由变化”“可达性变化”，可达性起点 c1、目标 `10.64.0.4`。 | 方向始终“基线 → 候选”；配置差异能定位 c2 接口关闭。路由/路径仅核对返回状态、范围、差异证据与限制，不强行断言路径数量。交换方向后应生成另一明确比较，不改写旧比较。 |
| P7 故障 | 在“故障模拟”选 `cisco-基线`，选择停用 c2 或其 GigabitEthernet0/1，填写方案名，创建派生快照。 | 派生任务及新快照可追踪；原基线仍存在且未改写，可按页面入口与基线比较。 |
| P8 BGP | 切到 `手测-BGP-ACL / example-live`，打开“BGP 会话”，查看模型状态和配置兼容性两种模式。 | 展示实际查询范围、结果来源和模型限制；不宣称在线邻居状态。 |
| P9 ACL | 在同一快照打开“ACL 流量测试” → “流量测试”，选择设备 `as2border1`、ACL `OUTSIDE_TO_INSIDE`，源 `10.12.11.1`、目标 `2.128.1.101`，执行；再查看“条件搜索”“规则诊断”。 | 结果显示被检查的设备、ACL、流量和匹配证据；局部 ACL 判定不等于端到端连通性。若候选列表名称不同，先以诊断/已解析 ACL 为准，记录差异。 |
| P10 结果恢复 | 记下 P4、P6、P9 的结果编号，刷新详情页；从“任务中心”重新打开。 | 历史结果仍指向原快照，页面能下载/查看已保存证据；切换当前快照不改变旧结果来源。 |

## 5. 专家功能逐步测试

1. 在 `example-live` 上打开“专家查询”，查看“已登记能力查询”。只选页面列出的“已开放能力”；填写该能力标记为必填的字段，展开“高级选项”并查看预计有效参数，再提交“运行专家查询”。记录能力名称、最终参数、任务号和结果号。若目录为空，记录为空态及环境版本，**不能**把未运行写为通过。
2. 在“虚拟 traceroute”把起点输入方式切到“专家表达式”，输入当前快照确实存在的设备（如 `as2border1`）；保留目标地址并提交。核对结果的生效范围及限制，再切回“设备与接口”，确认基础输入仍可用。
3. 在“ACL 流量测试”切换“设备选择方式”/“ACL 选择方式”为“专家表达式”，使用同一设备与 ACL 的字面名称，提交。核对范围没有跨越当前网络/快照；尝试未知 ACL 时应得到明确校验或空结果提示，而非复用上次结果。
4. 在专家查询页尝试添加未登记的 option 键或格式错误的 JSON。预期明确拒绝并保留可修正输入；不能执行任意 SDK 方法或覆盖网络、快照、引擎地址。修正后重新提交，确认成功结果与失败任务可区分。

## 6. 领导视图逐步测试

1. 点击技术工作台右上角“领导视图” → “总览”。空库时应显示“未检查/暂无快照”；导入后列出三个共享网络、最新就绪快照、解析/任务状态。点 `手测-Cisco四设备` 查看网络详情，逐级打开保存结果；总览不应凭配置自动给出健康分。
2. 以管理员打开“业务关注项”，所属网络选 `手测-Cisco四设备`，点“新增关注项”。名称填 `核心业务 c1→c4`，重要程度选“高”，关键流量起点 `c1`、目的 `10.64.0.4`，保存。打开“查看范围”，记映射版本。切到普通成员窗口，确认可查看、不可修改；管理员再修改描述，确认版本增加且旧版本可查看。
3. 打开“自主检查”，检查网络选 `手测-Cisco四设备`、配置快照选 `cisco-基线`。先选“配置质量” → “开始检查”；任务完成后依次打开结论、影响/检查范围、证据及“技术详情”，刷新详情 URL，内容应可恢复。
4. 在同页逐一检查“设备清单”“接口清单”“路由检查”（网段 `10.64.0.0/24`）“最长前缀匹配”（地址 `10.64.0.4`）“虚拟连通性”（起点 `c1`，目的 `10.64.0.4`）。连通性可从第 2 步的关注项预填，但必须核对本次网络、快照和范围；查看记录是否保留映射版本。任何未执行项都应保持“未检查”。
5. 继续选“网络拓扑”，先三层、再 OSPF；查看局部图、聚焦设备和关系证据。换到 `手测-BGP-ACL / example-live`，依次选“BGP 会话”与“ACL 流量检查”；ACL 输入源 `10.12.11.1`、目的 `2.128.1.101`、名称 `OUTSIDE_TO_INSIDE`。专家能力说明只引导到技术工作台，不应提供任意 SDK 调用。
6. 打开“变更与故障”，网络选 `手测-Cisco四设备`，左侧基线 `cisco-基线`、右侧候选 `cisco-c2链路关闭`，点“创建固定比较”。在比较详情依次检查配置、路由、可达性变化；可达性起点 `c1`，目的 `10.64.0.4`。确认界面一直标注固定方向、范围及截断/模型限制。再点“模拟设备或接口故障”，以基线创建停用 c2 的派生快照，并从入口建立基线/派生比较。
7. 完成至少一项检查后打开“固定汇报” → “创建固定汇报”，选择网络、快照和已完成结果，标题 `Cisco四设备手测汇报`，人工备注 `仅用于配置模型演示`，点“生成固定汇报”。打开详情和“会议视图”，检查大屏展示与浏览器打印/另存 PDF。修改关注项或再运行检查后刷新旧汇报：旧范围、映射版本和事实应保持固定；修订标题/人工备注应生成新版本，不能改写系统事实。
8. 在普通成员窗口打开同一汇报链接，检查团队内可读；切回“技术工作台”查看原始结果。分别在深、浅主题下检查总览、检查详情和会议视图是否可读；刷新后再次确认模式入口和主题行为。

## 7. 记录、停止与清理

最小记录表：`编号 | 操作人/角色 | 网络/快照 | 输入范围 | 任务/结果/汇报编号 | 预期 | 实际 | 截图/日志 | 通过/失败/未测`。特别记录首次改密、双用户权限、状态恢复、同网络比较方向、旧汇报版本、空结果/模型限制。遇到“服务尚未就绪”时记页面 URL、时间、请求编号和 `ready` HTTP 状态，再查本实例日志；不得仅点“重试”后忽略首次故障。

结束后从仓库根目录运行：

```bash
web/backend/.venv/bin/python web/scripts/deploy.py stop --state web/.runtime/manual-acceptance
```

`stop` 保留测试数据以便复核。确定不再需要数据时，用本实例 `deployment.json` 中的 `project` 与同目录 `compose.env` 执行 `docker compose --env-file <state>/compose.env -p <project> -f web/deploy/compose.yaml down --volumes --remove-orphans`，再删除该测试 state 目录；**不要**对其他 Compose 项目、卷或已有团队环境使用此清理命令。
