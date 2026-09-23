# Python 客户端（Pybatfish）使用手册

## 1. 边界与版本

Pybatfish 是 Batfish 服务的 Python SDK，源码和发布流程位于独立的
[`batfish/pybatfish`](https://github.com/batfish/pybatfish) 仓库。本仓库的
[`python`](../../python) 目录只管理 Bazel 内部 Python 工具依赖，不包含 SDK 源码。

当前服务端版本为 `0.36.0`；官方在线文档当前也显示 Pybatfish `0.36.0`。实际部署时应
记录服务端镜像/JAR 和 SDK 的版本，并在升级后重新运行关键验证。用户环境要求 Python
3.10 或更高，仓库的 Bazel Python 3.14 工具链不等于 Pybatfish 的强制版本。

## 2. 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install pybatfish
python -c 'from importlib.metadata import version; print(version("pybatfish"))'
```

在 CI 中应固定经过验证的版本，例如：

```text
pybatfish==0.36.0
pandas>=2.0,<3
```

是否固定 pandas 取决于调用方是否直接依赖 DataFrame dtype/展示格式；Pybatfish API 和
DataFrame 输出契约不是同一层稳定性。

## 3. 启动服务并建立 Session

先按[部署指南](deployment-guide.md)启动服务。REST v2 默认监听 `9996`：

```python
from pybatfish.client.session import Session

bf = Session(host="localhost")
print(bf.list_networks())
```

远端、TLS 或自定义端口：

```python
bf = Session(
    host="batfish.example.net",
    port=9996,
    ssl=True,
    verify_ssl_certs=True,
    api_key="replace-with-secret",
    timeout=120,
)
```

默认 API key 仅适合无鉴权的本地开发环境。生产环境应在 coordinator 前配置鉴权与 TLS，
不要在代码库中提交 key。代理或额外 `requests` 参数可通过 `proxies` 和 `request_kwargs`
传入。

## 4. Network、Snapshot 与输入

- **network**：逻辑网络容器，可包含多个时间点或候选方案。
- **snapshot**：不可变地表示一个分析状态；包含配置和可选补充数据。
- **reference snapshot**：差异问题的基线。

使用仓库样例：

```python
from pathlib import Path
from pybatfish.client.session import Session

bf = Session(host="localhost")
bf.set_network("development-guide-demo")

snapshot_dir = Path("networks/example")
bf.init_snapshot(snapshot_dir, name="baseline", overwrite=True)

print(bf.network)   # development-guide-demo
print(bf.snapshot)  # baseline
```

`overwrite=True` 会删除同名 snapshot 后重建，适合可重复的本地/CI 演示，不适合把历史同名
状态当审计记录的生产流程。生产建议使用 commit SHA、变更单或时间戳命名。

切换已存在快照：

```python
bf.set_network("development-guide-demo")
bf.set_snapshot("baseline")
print(bf.list_snapshots())
```

## 5. 初始化质量门

`init_snapshot()` 返回名称只说明工作完成，不说明所有配置都被正确理解。每次初始化至少检查：

```python
parse_status = bf.q.fileParseStatus().answer().frame()
issues = bf.q.initIssues().answer().frame()

print(parse_status[["File_Name", "Status", "File_Format"]])
print(issues)
```

推荐 CI 策略：

1. 所有预期配置文件必须出现在 `fileParseStatus`；
2. 不允许 `FAILED` / `UNKNOWN` / `UNSUPPORTED`；
3. 对 `PARTIALLY_UNRECOGNIZED` 设显式 allowlist，并审阅源行；
4. `initIssues` 中新增 red flag/unimplemented warning 使任务失败；
5. 保存表格为构建产物，便于追踪 parser 覆盖变化。

## 6. 问题调用模型

统一调用形式是：

```python
question = bf.q.routes(nodes="/core/")
answer = question.answer(snapshot="candidate", reference_snapshot="baseline")
frame = answer.frame()
```

在 IPython/Jupyter 中输入 `bf.q.` 后补全可查看已加载问题；标准 Python 可使用
`help(bf.q.routes)`。问题参数通常支持 Batfish specifier，而不只是字面名称：例如
`/core/` 是正则，`@role(...)`、`@enter(node[iface])` 是结构化选择器。

### 6.1 配置和接口

```python
nodes = bf.q.nodeProperties(nodes="/border/").answer().frame()
interfaces = bf.q.interfaceProperties(
    nodes="/border/",
    interfaces="/Ethernet/",
).answer().frame()

print(nodes.head())
print(interfaces[["Interface", "Active", "Primary_Address"]].head())
```

### 6.2 路由与会话

```python
routes = bf.q.routes(
    nodes="/core/",
    network="90.90.90.0/24",
    vrfs="default",
).answer().frame()

bgp = bf.q.bgpSessionCompatibility().answer().frame()
lpm = bf.q.lpmRoutes(ip="2.34.201.10").answer().frame()
```

`routes()` 需要数据平面，首次调用可能触发计算；结果持久化后同一 snapshot 的后续调用通常
更快。过滤尽量放在问题参数中，避免先下载整张大表再用 pandas 过滤。

### 6.3 虚拟 traceroute

```python
from pybatfish.datamodel import HeaderConstraints

traces = bf.q.traceroute(
    startLocation="host1",
    headers=HeaderConstraints(
        dstIps="1.0.2.2",
        ipProtocols=["tcp"],
        dstPorts=[443],
    ),
    maxTraces=5,
).answer().frame()

print(traces[["Flow", "Traces", "TraceCount"]])
```

这不是向真实网络发包。Batfish 从模型计算所有符合约束的路径，hop 中会包含使用的 route、
ACL/NAT 动作和最终 disposition。单向 `traceroute` 不证明回程可用；需要往返语义时使用
`bidirectionalTraceroute` 或可达性问题。

### 6.4 ACL/防火墙规则

```python
flow = HeaderConstraints(
    srcIps="10.0.0.10",
    dstIps="192.0.2.10",
    ipProtocols=["tcp"],
    dstPorts=[443],
)

result = bf.q.testFilters(
    nodes="edge1",
    filters="@in(edge1[Ethernet1])",
    headers=flow,
).answer().frame()
```

`testFilters` 测试给定 flow；`searchFilters` 在约束空间内寻找匹配/反例；
`filterLineReachability` 检查规则是否被前序规则遮蔽。三者解决的问题不同。

## 7. 差异分析与故障模拟

### 7.1 两个完整目录

```python
bf.set_network("change-1234")
bf.init_snapshot("snapshots/baseline", name="baseline", overwrite=True)
bf.init_snapshot("snapshots/candidate", name="candidate", overwrite=True)

route_diff = bf.q.routes().answer(
    snapshot="candidate",
    reference_snapshot="baseline",
).frame()

reachability_diff = bf.q.differentialReachability().answer(
    snapshot="candidate",
    reference_snapshot="baseline",
).frame()
```

对大范围差异可达性应添加 `HeaderConstraints` 和 path constraints，缩小业务范围并限制
`maxTraces`；无限制搜索虽有价值，但结果更难审阅。

### 7.2 Fork snapshot 模拟故障

```python
bf.set_snapshot("baseline")
bf.fork_snapshot(
    base_name="baseline",
    name="edge1-down",
    deactivate_nodes=["edge1"],
    overwrite=True,
)

impact = bf.q.differentialReachability().answer(
    snapshot="edge1-down",
    reference_snapshot="baseline",
).frame()
```

也可使用 `deactivate_interfaces`、`restore_nodes`、`restore_interfaces` 或 `add_files`。
fork 是服务端对象操作，不会修改原始 snapshot 目录。

## 8. 自动化脚本范式

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

from pybatfish.client.session import Session


def main() -> int:
    bf = Session(host="localhost", timeout=300)
    bf.set_network("ci-network")
    bf.init_snapshot(
        Path("build/snapshot"),
        name="candidate",
        overwrite=True,
    )

    issues = bf.q.initIssues().answer().frame()
    if not issues.empty:
        print(issues.to_string(index=False), file=sys.stderr)
        return 1

    undefined = bf.q.undefinedReferences().answer().frame()
    if not undefined.empty:
        print(undefined.to_string(index=False), file=sys.stderr)
        return 2

    print("Batfish validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

真实 CI 中通常需要对已知告警做结构化 allowlist，而不是要求 `initIssues` 永远为空。不要用
字符串化后的整表做脆弱的 golden comparison；选择稳定列、排序、标准化集合列后再比较。

## 9. 性能与可靠性

- 复用一个 `Session`，不要为每个问题重新建立并加载模板。
- 同一内容用同一 snapshot 名不会自动保证缓存正确；通过 API 初始化/覆盖，不要改内部存储。
- 先运行小范围问题确认输入，再运行全网 BDD 或 dataplane 问题。
- 设置合理 `timeout`；禁用超时会让网络故障表现为永久等待。
- 对 DataFrame 显式排序再生成报告，服务端不保证所有集合/行都适合按原始顺序比较。
- 保留 `initIssues`、work log 和服务端版本，答案异常时这三项最有诊断价值。

## 10. 常见错误

| 症状 | 先检查 |
| --- | --- |
| 连接被拒绝 | 服务是否监听 9996、容器是否映射 `-p 9996:9996` |
| 问题方法不存在 | Session 是否加载问题模板、服务端与 SDK 是否兼容、`questions` 目录是否配置 |
| snapshot 初始化成功但结果为空 | `fileParseStatus`、`initIssues`、目录层级和格式识别 |
| 第一个 routes/reachability 很慢 | 是否首次触发 dataplane、内存是否足够、输入规模 |
| 差异问题报 reference 缺失 | `.answer(reference_snapshot="...")` 是否设置 |
| 正则未命中 | specifier 语法与字面字符串差异，先用 resolve specifier 类问题验证 |

## 11. 官方参考

- [Pybatfish 文档](https://pybatfish.readthedocs.io/en/latest/)
- [Getting Started notebook](https://pybatfish.readthedocs.io/en/latest/notebooks/linked/getting-started-with-batfish.html)
- [Interacting with the service](https://pybatfish.readthedocs.io/en/latest/notebooks/interacting.html)
- [Packet forwarding](https://pybatfish.readthedocs.io/en/latest/notebooks/forwarding.html)
- [Differential questions](https://pybatfish.readthedocs.io/en/latest/notebooks/differentialQuestions.html)
- [Pybatfish 源码](https://github.com/batfish/pybatfish)
