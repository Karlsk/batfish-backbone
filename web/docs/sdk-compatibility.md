# MVP-01 SDK 兼容性基线

日期：2026-09-25（Asia/Shanghai）。结论：本篇验收通过，7 项测试通过、0 失败、0 错误、0 跳过，最终 pytest 用时 6.14 秒。这里验证 SDK 与引擎契约，不代表 Web API 或 UI 已实现。

## 固定版本与来源

| 项目 | 实际值 |
| --- | --- |
| 引擎源码 revision | `7d0deeeac4a09973b3876327f6aef721ee12f955`，包含本仓库 Huawei/H3C 支持 |
| 构建 | Bazel 9.2.0，`//projects/allinone:allinone_main_deploy.jar`，本次重新构建检查通过；未改 Java 源码 |
| JAR SHA-256 | `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193` |
| 引擎版本接口 | `Batfish=0.36.0`、`api_version=0.0.0`；版本字符串不能替代 revision/JAR 摘要 |
| Python / SDK / pytest | `3.12.12` / `2026.9.17.3748` / `8.4.2` |
| 隔离环境 | `127.0.0.1:19996`，全新临时存储，JVM `-Xms256m -Xmx4g` |
| 模板 | 与仓库一致，共 75 个：27 stable、48 experimental |

原设计候选 `pybatfish==0.36.0` 无可安装发行版，uv 解析依赖失败；这不是引擎调用失败。该编号出现在文档/引擎版本中，Python 包使用另一套发行号。改用 [PyPI 固定发行版](https://pypi.org/project/pybatfish/2026.9.17.3748/)，没有替换为官方引擎镜像或禁用 Python 断言。

[结构化证据](evidence/mvp-01-sdk-baseline.json) 保存本次环境包版本、构建信息、75 个模板的参数、公开 Session 方法签名、16 次查询的上下文/参数/schema/原始行/类型/耗时，以及初始化、错误和后台任务观测。完整包列表用于复核；MVP-02 才创建应用锁文件。

## 实测契约

| 能力 | 观测与后续约束 |
| --- | --- |
| 网络 | `set_network(name)` 对不存在名称创建网络，对已存在名称选择网络；返回名称字符串。已通过列表核实创建与重复选择。 |
| 初始化 | `init_snapshot(..., overwrite=False)` 同步等待解析后返回快照名字符串；不是诊断结果对象，也不返回公开初始化任务 ID。 |
| 初始化告警 | 含合成未知命令的快照仍返回名称；`fileParseStatus` 为 `PARTIALLY_UNRECOGNIZED`，`parseWarning` 与 `initIssues` 有证据。本次未自动记录 warning 级日志，不能用“返回成功/无日志”代替质量判断。 |
| 不可覆盖 | 同名初始化且 `overwrite=False` 抛 `ValueError`；后续仍可读取原快照的节点和原始配置。 |
| 已存在快照 | `list_snapshots(verbose=True)` 返回名字与初始化元数据，观测到 `PARSED`/`DATAPLANED`。`get_snapshot()` 返回会话选中名称，本身不能证明远端执行完成。 |
| 会话隔离 | 两个独占 Session 使用相同逻辑显示标签 `baseline`、不同内部 network/snapshot；一次设置后 A/B/A/B 交错调用默认快照，各自返回 `10.0.0.2/32` 或 `10.0.0.22/32`。显示标签只是测试元数据，不是已实现的 Web 功能。 |
| 模板加载 | `Session` 自动从引擎加载；`session.q.list()` 列举。全部模板可构造，核心 experimental 查询实际执行成功；SDK 会规范化参数说明的空白/句号，比较时只归一化该已查明差异。 |
| 缺失能力 | 未加载的问题名可通过目录检测，直接访问抛 `AttributeError`；未知参数抛 `QuestionValidationException`；查询不存在快照抛 `HTTPError`。不能转为空表或伪装成功。 |
| 后台分析 | `q.nodeProperties(..., question_name=...).answer(snapshot=..., background=True)` 返回 UUID 字符串。新 Session 选择同一 network 后，`get_work_status(id)` 观测到 `ASSIGNED → TERMINATEDNORMALLY`。 |
| 已有答案 | 新 Session 通过 `get_answer(question_name, snapshot)` 取回完整结果；通过 `get_snapshot_input_object_text` 取回原始合成配置。后台查询名须保存，不能仅保存 work ID。 |
| 不完整工作 | `list_incomplete_works()` 本次返回 `{"worklist": "[]"}`；value 是 JSON 字符串，并非直接数组。这里只记录单次观察，不将其用于自动释放引擎占用。 |

公开后台分析与答案读取已确认，不等于已经验证 worker 崩溃窗口、引擎重启后的任务持久性或取消运行任务。公开 Session 方法未提供取消入口；`init_snapshot` 没有公开 `background` 参数。MVP-09 继续按 unknown 占用/管理员对账设计，不扩大为自动接管，也不调用私有 `_init_snapshot`。

## 查询、参数与结果

合成拓扑：[r1 Huawei](../backend/tests/fixtures/small_network/configs/r1.cfg) 与 [r2 H3C](../backend/tests/fixtures/small_network/configs/r2.cfg)，通过 `192.0.2.0/30` 连接，LoopBack 分别为 `10.0.0.1/32` 和 `10.0.0.2/32`，两端有对端 LoopBack 的静态路由。

| 查询 | 本次参数/断言 | 结果结构要点 |
| --- | --- | --- |
| nodeProperties | `properties=Configuration_Format`，2 节点且厂商正确 | Node → str，Configuration_Format → str |
| interfaceProperties | `properties=Primary_Address`，4 个预期 IPv4 地址 | Interface → SDK Interface 对象，Primary_Address → str |
| routes | `nodes=r1, network=10.0.0.2/32`，1 条 static | Next_Hop → NextHopIp 对象；保留类型，不能只存展示字符串 |
| lpmRoutes | `nodes=r1, ip=10.0.0.2`，命中 `/32` | Node/VRF/Ip/Network/Num_Routes；没有完整下一跳明细列 |
| traceroute | r1、ICMP、源 10.0.0.1、目标 10.0.0.2 | Flow 对象、ListWrapper 包含 Trace；1 条 ACCEPTED，hop 顺序 r1→r2 |
| 初始化诊断 | 正常和未知命令两类快照 | 状态、行号、来源文件和嵌套 FileLines；空表仍有列 metadata |

测试检查原始 Answer 字典可进行严格 JSON 编码；`frame()` 内的 Interface/NextHop/Flow/Trace/ListWrapper 不是普通 JSON 类型。未来 controller 应按 schema 转换，不能直接返回 DataFrame。该基线没有穷举其他下一跳类型、多 VRF、默认路由或各厂商全部能力；这些继续由 MVP-14/15 等 spec 验证。

## 阻塞、超时与限制

- 固定 SDK 的默认请求 timeout 为 30 秒；本套实际引擎 Session 显式设为 10 秒。该值约束单次 HTTP 请求，不是整个初始化/分析任务的期限。
- 单独的受控本机 HTTP 测试使用 `timeout=0.03`，前次请求变慢后发生 GET 自动重试；3 次请求后成功，总耗时约 1.67 秒。服务端请求在客户端等待超时后继续完成。这个测试不冒充引擎任务取消验证。
- 源码核验：该发行版对幂等 HTTP 方法启用重试（上限 10 次、退避因子 0.8）；工作轮询直到终态，没有应用级整体等待预算。未显式配置 timeout 时，上传路径还可采用不同默认值。Web 必须显式传入配置，并单独处理工作预算与 unknown 状态。
- 本次仅合成两台设备，没有容量/100 台性能承诺，没有在线设备探测；引擎崩溃恢复、所有网络故障重试和运行中取消均不在本篇“已验证”范围。

## 复现

在仓库根目录构建。若需要使用本机已有 Bazel 下载缓存，可另加 `--distdir=/private/tmp/h3c-bazel.l0kCKY`；这个参数不是其他机器的必需路径。

```bash
bazel build //projects/allinone:allinone_main_deploy.jar --jobs=6
export MVP01_REPO="$PWD"
export MVP01_RUN="$(mktemp -d "${TMPDIR:-/tmp}/batfish-mvp01.XXXXXX")"
export BATFISH_TEST_HOST=127.0.0.1
export BATFISH_TEST_PORT=19996
export BATFISH_TEST_PREFIX=mvp01-baseline
export BATFISH_TEST_ISOLATED=1
export BATFISH_TEST_MANIFEST="$MVP01_RUN/engine-manifest.json"
export BATFISH_TEST_EVIDENCE="$MVP01_RUN/evidence.json"
python3 - <<'PY'
import hashlib, json, os, subprocess
from pathlib import Path
root = Path(os.environ['MVP01_REPO'])
jar = root / 'bazel-bin/projects/allinone/allinone_main_deploy.jar'
manifest = {
    'engine_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'jar_sha256': hashlib.sha256(jar.read_bytes()).hexdigest(),
    'host': os.environ['BATFISH_TEST_HOST'],
    'port': int(os.environ['BATFISH_TEST_PORT']),
}
Path(os.environ['BATFISH_TEST_MANIFEST']).write_text(json.dumps(manifest, indent=2) + '\n')
PY
java -Xms256m -Xmx4g -jar bazel-bin/projects/allinone/allinone_main_deploy.jar \
  -runclient false -loglevel error \
  -coordinatorargs "-workbindhost $BATFISH_TEST_HOST -workv2port $BATFISH_TEST_PORT -containerslocation $MVP01_RUN/containers -templatedirs $MVP01_REPO/questions" \
  >"$MVP01_RUN/engine.log" 2>&1 &
MVP01_PID=$!
trap 'kill "$MVP01_PID" 2>/dev/null || true' EXIT
```

端口须空闲；确认本次启动的进程仍存活且版本接口可用后，在同一个终端继续。失败时查看临时目录的日志，不能改连团队引擎。

```bash
kill -0 "$MVP01_PID"
curl --fail --silent "http://$BATFISH_TEST_HOST:$BATFISH_TEST_PORT/v2/version"
cd "$MVP01_REPO/web/backend"
uv run --no-project --python 3.12 \
  --with pybatfish==2026.9.17.3748 --with pytest==8.4.2 \
  pytest tests/integration/test_sdk_baseline.py -q --junitxml="$MVP01_RUN/pytest.xml"
kill "$MVP01_PID"
wait "$MVP01_PID" || true
trap - EXIT
```

每次运行需使用新的 evidence 文件。测试故意保留随机前缀合成网络，便于失败调查；关闭本次临时引擎后其目录可由操作者清理。manifest 是启动者的构建来源声明，测试不能独立从服务版本字符串证明其 revision，必须同时保存构建/启动记录与 JAR 摘要。

## 执行与审查记录

1. 原候选包安装失败，记录后更换为固定发行版。
2. 未提供隔离配置运行：pytest setup 明确报错，没有连接默认引擎，没有 skip。
3. 首轮实际引擎：5 通过、2 失败；失败来自模板说明规范化和 HTTP 自动重试，与测试原假设不同，按源码和观测修正。
4. 第二轮：7 通过。只读审查指出默认 snapshot 隔离断言与证据覆盖两项缺口，已修正。
5. 最终完整运行：7 通过，独立审查确认 16 次调用及默认快照交错证据完整；原始 JUnit/日志位于本机 `/private/tmp/batfish-mvp01-birscy6n/`，可分享证据已归档到本文相邻 JSON。
6. 本次临时 Batfish 进程已关闭，确认 19996 端口无监听；文档链接、Python 语法及 `git diff --check` 通过。

本篇通过后可以开始 MVP-02；本次交付不包含后续篇目的实现。
