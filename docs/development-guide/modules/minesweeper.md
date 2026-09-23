# minesweeper 模块

## 职责

[`projects/minesweeper`](../../../projects/minesweeper) 对路由策略进行符号分析。它把路由属性和
策略执行编码为 BDD，用于搜索满足/违反策略的路由、比较策略行为以及为反例生成具体 route。
顶层聚合目标为 `//projects/minesweeper:minesweeper`。

不要与 packet reachability 混淆：Minesweeper 的变量主要是 prefix、protocol、metric、local
preference、MED、tag、community、AS path 等**路由属性**；packet BDD 表示 src/dst IP、port、
protocol 等**报文字段**。

## 核心类型

- [`BDDRoute`](../../../projects/minesweeper/src/main/java/org/batfish/minesweeper/bdd/BDDRoute.java)：
  符号路由的字段集合。
- [`TransferBDD`](../../../projects/minesweeper/src/main/java/org/batfish/minesweeper/bdd/TransferBDD.java)：
  解释 routing-policy statement/expr，将输入 route 变成输出约束。
- [`TransferResult`](../../../projects/minesweeper/src/main/java/org/batfish/minesweeper/bdd/TransferResult.java)：
  接受/拒绝、输出 route 和路径条件。
- [`ConfigAtomicPredicates`](../../../projects/minesweeper/src/main/java/org/batfish/minesweeper/ConfigAtomicPredicates.java)：
  从配置收集 community/AS-path regex 并构建原子谓词。
- [`RegexAtomicPredicates`](../../../projects/minesweeper/src/main/java/org/batfish/minesweeper/RegexAtomicPredicates.java)：
  把重叠正则语义分割为互斥原子集合。
- collectors：收集 policy 调用、community、AS path、prefix list 等依赖。

## 数据流

```text
VI Configuration + RoutingPolicy
 → collectors 找到被引用的 policy/prefix/community/as-path 表达式
 → ConfigAtomicPredicates 划分 regex 语义空间
 → BDDRoute 为字段与原子谓词分配 BDD 变量
 → TransferBDD.visit(statement/expression)
    ├─ match 产生 path constraint
    ├─ set/prepend/delete 更新符号字段
    ├─ call 进入被调 policy
    └─ return/exit 形成 permit/reject result
 → 约束求交/求异
 → ModelGeneration 从 sat assignment 构造具体 BGP route 反例
```

## 原子谓词原理

两个 community regex 可能部分重叠。若直接给每个 regex 一个独立布尔变量，会允许逻辑上不可能
的赋值。`RegexAtomicPredicates` 将所有 regex 划分成互斥且完备的原子区域；每个原子区域用一个
BDD 变量表示，原 regex 等于若干原子变量的并。AS path 使用同样思路，并需处理 prepend 对
正则语言的变换。

## TransferBDD 原理

`TransferBDD` 是 routing policy 的符号解释器：

- `If` 将当前路径条件分成 guard 与非 guard 两支；
- `SetLocalPreference` 等更新 `BDDRoute` 字段；
- `CallStatement/CallExpr` 解析被调 policy，并维护 call/return 上下文；
- community set/match 和 AS-path match 映射到原子谓词约束；
- permit/reject 终止相应路径；未终止路径按 policy 默认语义处理。

输出不是一个 route，而是一组 `(path condition, output route, action)`。把两条 policy 的 action
或输出字段做差并调用 `satOne()`，可得到能区分它们的具体输入。

## 概念示例：搜索被 permit 的路由

```java
RoutingPolicy policy = configuration.getRoutingPolicies().get("IMPORT");
ConfigAtomicPredicates aps = new ConfigAtomicPredicates(
    ImmutableList.of(Map.entry(configuration, ImmutableList.of(policy))),
    ImmutableSet.of(),
    ImmutableSet.of());
TransferBDD transfer = new TransferBDD(aps);
List<TransferReturn> paths = transfer.computePaths(policy, false);

for (TransferReturn path : paths) {
  if (path.getAccepted() && !path.getInputConstraints().isZero()) {
    BDD witness = path.getInputConstraints().satOne();
    // ModelGeneration 可将 witness 与 outputRoute 解码成具体 route；随后释放临时 BDD。
    witness.free();
  }
}
```

该片段省略 imports 和最终模型解码；编写生产代码时参考当前
[`searchroutepolicies`](../../../projects/minesweeper/src/main/java/org/batfish/minesweeper/question/searchroutepolicies)
调用链和现有测试，不要仅复制概念片段。

Pybatfish 用户示例：

```python
from pybatfish.datamodel.route import BgpRouteConstraints

result = bf.q.searchRoutePolicies(
    nodes="edge1",
    policies="IMPORT",
    inputConstraints=BgpRouteConstraints(prefix=["10.0.0.0/8:8-32"]),
    action="permit",
).answer().frame()
```

## 测试

```bash
bazel test //projects/minesweeper/...
bazel test //projects/minesweeper/src/test/java/org/batfish/minesweeper/question/searchroutepolicies/...
bazel test //projects/question/src/test/java/org/batfish/question/testroutepolicies/...
```

应覆盖 permit/reject、nested call、default action、prefix range 边界、community set 操作、AS-path
prepend、unsupported expression、递归 policy 和具体 witness 回放。符号结果必须用 concrete policy
evaluation 回放验证，避免编码与解码同时犯同一错误。

## 修改注意事项

- 新 routing-policy AST 节点进入 `common` 后，必须明确 symbolic semantics；不能默认为 identity。
- 原子谓词数量决定 BDD 规模；新增 regex 集合前评估去重和依赖闭包。
- BDD 生命周期遵循 `projects/bdd` ownership 规则，特别注意 destructive `xxxWith`。
- 反例生成的 route 必须满足真实 datamodel 不变量，才能被 concrete evaluator 接受。
