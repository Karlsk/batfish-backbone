# symbolic 模块

## 职责

[`projects/symbolic`](../../../projects/symbolic) 定义 packet 符号可达性使用的**状态语言**，而不
执行完整图构造或 BDD 固定点。顶层目标 `//projects/symbolic:symbolic` 导出 core 和 state。

核心类型：

- [`IngressLocation`](../../../projects/symbolic/src/main/java/org/batfish/symbolic/IngressLocation.java)：
  VRF/interface/interface-link 的入口描述。
- [`StateExpr`](../../../projects/symbolic/src/main/java/org/batfish/symbolic/state/StateExpr.java)：所有状态的
  visitor 接口。
- [`StateExprVisitor`](../../../projects/symbolic/src/main/java/org/batfish/symbolic/state/StateExprVisitor.java)：
  对状态进行解释/变换的双分派接口。
- [`state` package](../../../projects/symbolic/src/main/java/org/batfish/symbolic/state)：入口、接口前后、
  VRF 前后、出边、ACL drop、accept 和最终 disposition 等值对象。

## 状态机原理

符号可达性把“报文在网络哪里、正处于哪个处理阶段”从 BDD 报文集合中分离：

```text
StateExpr S -- Transition T(BDD→BDD) --> StateExpr S'
```

状态回答“位置和阶段”，transition 回答“哪些报文能走这条边、字段如何变化”。例如：

```text
OriginateVrf
 → PostInVrf
 → PreOutVrf
 → PreOutEdge
 → PreInInterface
 → PostInInterface
 → NodeAccept / DropAclIn / ...
```

实际路径会因 ACL、packet policy、session、NAT、邻接和 FIB 分支增加中间状态。

终态包括 `Accept`、`DeliveredToSubnet`、`ExitsNetwork`、`NeighborUnreachable`、
`InsufficientInfo`、`BlackHole`、`DropAclIn/Out`、`DropNoRoute`、`DropNullRoute` 等。节点级和
接口级状态分别保留定位分析所需的粒度。

## 为什么单独成模块

- 状态类型可序列化、可比较，能作为 graph map/set key；
- 不依赖具体 BDD factory，便于图结构与布尔运算解耦；
- visitor 强制所有消费者显式处理新增状态；
- `batfish/bddreachability` 可以负责边和 transition，question 只消费查询结果。

## 示例：Visitor

```java
final class StateKindVisitor implements StateExprVisitor<String> {
  @Override
  public String visitAccept(Accept accept) {
    return "success";
  }

  @Override
  public String visitDropAclIn(DropAclIn drop) {
    return "denied";
  }

  // 其余状态必须按接口补齐。
}

String kind = state.accept(new StateKindVisitor());
```

方法名以当前 `StateExprVisitor` 接口为准。新增 `StateExpr` 时编译器会暴露所有需要更新的
visitor，这是 sealed-like 穷举约束的主要价值。

## 与 bddreachability 的数据流

[`BDDReachabilityAnalysisFactory`](../../../projects/batfish/src/main/java/org/batfish/bddreachability/BDDReachabilityAnalysisFactory.java)
读取配置、forwarding analysis、topology、ACL/NAT/session，生成 `StateExpr` 图和每条边的
`Transition`；
[`BDDReachabilityAnalysis`](../../../projects/batfish/src/main/java/org/batfish/bddreachability/BDDReachabilityAnalysis.java)
对图做前向/反向可达性计算。`symbolic` 提供节点词汇，核心模块提供网络语义。

## 测试

```bash
bazel test //projects/symbolic/...
bazel test //projects/batfish/src/test/java/org/batfish/bddreachability/...
```

新增状态必须测试 equality/hash、visitor dispatch、图边生成和至少一个端到端 disposition。

## 修改注意事项

- 状态字段必须足够区分网络位置，但不要携带庞大 Configuration/FIB 对象。
- 任何新状态都需更新 visitor、graph factory、query/result 映射和 serialization。
- 状态名不是用户 disposition；多个内部状态可能汇总成一个外部结果。
