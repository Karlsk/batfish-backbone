# 构建与部署指南

## 1. 部署形态

| 形态 | 用途 | 产物/入口 |
| --- | --- | --- |
| Bazel 直接运行 | 日常开发、调试、单测 | `//projects/allinone:allinone_main` |
| Deploy JAR | CI 产物、受控 JVM 环境 | `allinone_main_deploy.jar` |
| `batfish/batfish` 镜像 | 只运行 Batfish 服务 | 外部 `batfish/docker` 仓库 |
| `batfish/allinone` 镜像 | 服务 + Jupyter/Pybatfish 示例 | 外部 `batfish/docker` 仓库 |

本仓库没有 Dockerfile。镜像由独立的
[`batfish/docker`](https://github.com/batfish/docker) 仓库构建；不要在本仓库假设存在
`docker build .` 所需上下文。

## 2. 开发环境前置条件

- JDK 21 最低、JDK 25 推荐；Bazel 构建自身使用 tool Java 21，目标 runtime 为
  `remotejdk_25`，见 [`.bazelrc`](../../.bazelrc)。
- Bazelisk 推荐，它会读取 [`.bazelversion`](../../.bazelversion) 中的 `9.2.0`。
- Git。
- Python 3.10+ 仅在使用 Pybatfish/pre-commit 时需要；Bazel Python 工具链由
  [`MODULE.bazel`](../../MODULE.bazel) 配置。
- Docker/Podman 仅在构建或运行容器时需要。

确认环境：

```bash
java -version
bazel --version
git status --short
```

macOS/Ubuntu 的包管理器细节见
[`docs/building_and_running`](../building_and_running/README.md)。

## 3. 依赖解析

Bzlmod 入口是 [`MODULE.bazel`](../../MODULE.bazel)，Maven lockfile 是
[`maven_install.json`](../../maven_install.json)，Python lockfile 是
[`python/requirements.txt`](../../python/requirements.txt)。首次构建需要网络下载 Bazel 模块、
JDK toolchain 和 Maven/Python 依赖。

不要手改生成的 lockfile：

- Java 依赖：修改 `MODULE.bazel` 后按仓库既有流程重新 pin。
- Python 工具依赖：修改 `python/requirements.in`，按
  [`python/README.md`](../../python/README.md) 运行 `pip-compile`。

## 4. 构建

从仓库根目录执行：

```bash
# 快速构建主要入口
bazel build //projects/allinone:allinone_main

# 可分发、包含运行时依赖的 deploy JAR
bazel build //projects/allinone:allinone_main_deploy.jar

# 只包含 Batfish 自有模块的 thin JAR（嵌入者自行提供三方依赖）
bazel build //projects/allinone:batfish_thin.jar

# 构建所有目标
bazel build //...
```

产物通常位于：

```text
bazel-bin/projects/allinone/allinone_main
bazel-bin/projects/allinone/allinone_main_deploy.jar
bazel-bin/projects/allinone/batfish_thin.jar
```

`thin_jar` 的依赖边界由 [`projects/allinone/BUILD.bazel`](../../projects/allinone/BUILD.bazel)
定义；它不适合直接 `java -jar` 当作完整发行包。

## 5. 本地开发部署

### 5.1 推荐脚本

```bash
tools/bazel_run.sh
```

脚本会构建 `allinone_main` 并带开发参数启动。阅读
[`tools/bazel_run.sh`](../../tools/bazel_run.sh) 了解当前默认值。

### 5.2 显式命令

```bash
mkdir -p containers

bazel run //projects/allinone:allinone_main -- \
  -runclient false \
  -coordinatorargs "-templatedirs $(git rev-parse --show-toplevel)/questions \
  -containerslocation $(git rev-parse --show-toplevel)/containers"
```

关键参数：

- `-runclient false`：不启动交互 Java client，进程作为服务常驻。
- `-templatedirs`：加载 `questions/stable` 等 JSON 模板；漏掉时 Pybatfish 的 `bf.q`
  不会得到完整问题集合。
- `-containerslocation`：coordinator/worker 的文件存储根目录。

不要把 `containers/` 提交到 Git。它是内部持久化结构，不是 snapshot 输入格式。

### 5.3 JVM 内存

```bash
bazel run --jvmopt=-Xms2g --jvmopt=-Xmx8g \
  //projects/allinone:allinone_main -- \
  -runclient false \
  -coordinatorargs "-templatedirs $(pwd)/questions -containerslocation $(pwd)/containers"
```

Bazel 的 `--jvmopt` 必须放在 `run` 与 target 之间；`--` 后是应用参数。大型网络的数据平面
和 BDD 分析高度依赖内存，容器内存限制也必须大于 JVM heap 并留出 native/OS 余量。

### 5.4 调试

```bash
bazel run \
  --jvmopt=-ea \
  --jvmopt=-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5009 \
  //projects/allinone:allinone_main -- \
  -runclient false \
  -coordinatorargs "-templatedirs $(pwd)/questions -containerslocation $(pwd)/containers"
```

只在受信任的开发网络暴露 JDWP；它等价于远程代码执行能力。IntelliJ 配置另见
[`docs/intellij_setup`](../intellij_setup/README.md)。

### 5.5 健康检查

```bash
curl --fail --silent http://localhost:9996/v2/version
```

然后按 [Python 客户端手册](python-client-guide.md)运行 `list_networks()` 和样例 snapshot。
进程存在不等于可用：至少验证 REST、模板加载、初始化和一个问题。

## 6. 测试与静态检查

```bash
# 全量测试
bazel test //...

# 按模块
bazel test //projects/coordinator/...
bazel test //projects/batfish/...
bazel test //projects/question/...

# PMD 与仓库格式/检查脚本
bazel test //projects/batfish/src/main/java/org/batfish:pmd
tools/run_checkstyle.sh
bazel run //tools/format:format.check

# 指定 JUnit 方法
bazel test \
  --test_filter=org.batfish.coordinator.WorkMgrServiceTest#getNonExistNetwork$ -- \
  //projects/coordinator:coordinator_tests
```

具体格式脚本参数会随仓库演进；运行前使用 `--help` 或阅读脚本。提交前流程见
[`docs/development/pr_preparation.md`](../development/pr_preparation.md)。

## 7. 使用官方镜像

快速启动：

```bash
docker pull batfish/allinone:latest

docker run --name batfish \
  --memory=8g \
  -v batfish-data:/data \
  -p 8888:8888 \
  -p 9996:9996 \
  -p 9997:9997 \
  batfish/allinone:latest
```

端口含义：

- `8888`：allinone 镜像内的 Jupyter（service-only 镜像没有）。
- `9996`：当前 REST v2 coordinator，Pybatfish 默认使用。
- `9997`：历史兼容端口；是否需要取决于镜像/客户端版本。

生产部署不要使用漂移的 `latest`；在验证环境解析实际 digest 后固定
`batfish/allinone@sha256:...` 或明确 tag，并把 Pybatfish 版本一起记录。

## 8. 从源码构建 Docker 镜像

镜像构建上下文来自外部仓库：

```bash
git clone https://github.com/batfish/docker.git
cd docker

docker build -t batfish/batfish:dev -f batfish/Dockerfile .
docker build -t batfish/allinone:dev -f allinone/Dockerfile .
```

构建逻辑可能下载已发布的 JAR，也可能提供指向 Batfish 源码/产物的参数。使用前阅读该
checkout 的 README 和 Dockerfile，不要假设当前本仓库 commit 会自动进入镜像。可靠流程是：

1. 固定 `batfish/batfish` 和 `batfish/docker` 两个 commit；
2. 明确 Dockerfile 使用的 JAR 来源与 SHA/digest；
3. 构建后在容器内或 `/v2/version` 核对版本；
4. 用固定 snapshot 跑初始化质量门与代表性问题；
5. 标记并推送到内部 registry。

运行 service-only 镜像：

```bash
docker run --rm --name batfish-service \
  --memory=8g \
  -v batfish-data:/data \
  -p 9996:9996 \
  batfish/batfish:dev
```

如果所用 Dockerfile 只暴露或启动不同端口，以该镜像仓库版本的配置为准。

## 9. Compose 示例

```yaml
services:
  batfish:
    image: ${BATFISH_IMAGE}
    restart: unless-stopped
    ports:
      - "127.0.0.1:9996:9996"
    volumes:
      - batfish-data:/data
    deploy:
      resources:
        limits:
          memory: 8G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9996/v2/version"]
      interval: 30s
      timeout: 5s
      retries: 5

volumes:
  batfish-data:
```

在 `.env` 或部署系统中把 `BATFISH_IMAGE` 设置为经过验证的完整 digest，例如
`batfish/batfish@sha256:<实际摘要>`。若镜像不包含 curl，改用镜像已有工具或在宿主/编排器
侧进行 HTTP probe。

## 10. 生产部署注意事项

- **安全**：默认开发 API key 不是安全边界。使用反向代理、TLS、网络 ACL 和真实鉴权；
  不向公网暴露 coordinator 或 JDWP。
- **资源**：大型 dataplane/BDD 任务可能占用大量 heap；同时限制任务并监控 GC、OOM 和磁盘。
- **持久化**：备份 `/data` 或实际 containers location；升级前做可恢复快照。
- **不可变性**：固定镜像 digest、SDK 版本、问题模板和输入；记录 `/v2/version`。
- **滚动升级**：先用代表性 snapshot 做解析/转换警告 diff 和关键问题 diff，再替换生产实例。
- **可观察性**：采集容器日志、work 日志、任务终态、初始化告警、延迟和存储增长。
- **清理**：通过 network/snapshot API 删除不再需要的数据，避免直接删除内部目录造成 ID 和
  元数据不一致。

## 11. 故障排查

| 问题 | 诊断顺序 |
| --- | --- |
| Bazel 下载失败 | 网络/代理、Bazelisk 版本、lockfile 是否未提交变化 |
| 编译提示 Java 版本 | `java -version`、`.bazelrc` toolchain、是否使用仓库根目录 |
| 9996 无响应 | 进程日志、端口映射、bind host、`/v2/version` |
| `bf.q` 缺少问题 | coordinator `templatedirs`、模板加载错误日志 |
| 初始化 OOM | heap、容器 limit、snapshot 大小、并发任务数 |
| 镜像内容不是本地代码 | Dockerfile 的 JAR 来源、镜像 digest 和 `/v2/version` |
| 重启后 network 消失 | volume 是否挂载到镜像实际数据路径 |
