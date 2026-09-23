# bdd 模块

## 职责

[`projects/bdd`](../../../projects/bdd) 是仓库内维护的 JavaBDD 实现，package 为
`net.sf.javabdd`。BDD（Binary Decision Diagram）用有序、规约的有向无环图表示布尔函数，
使集合交并差、存在量化、变量替换和可满足性操作可以在大量报文/路由取值上一次完成。

核心文件：

- [`BDD`](../../../projects/bdd/src/main/java/net/sf/javabdd/BDD.java)：布尔函数句柄和运算 API。
- [`BDDFactory`](../../../projects/bdd/src/main/java/net/sf/javabdd/BDDFactory.java)：变量、domain、
  factory 生命周期和运算入口。
- [`JFactory`](../../../projects/bdd/src/main/java/net/sf/javabdd/JFactory.java)：节点表、唯一表、缓存、
  垃圾回收和具体算法。
- [`BDDDomain`](../../../projects/bdd/src/main/java/net/sf/javabdd/BDDDomain.java)：多 bit 有限域。
- [`BDDPairing`](../../../projects/bdd/src/main/java/net/sf/javabdd/BDDPairing.java)：变量替换映射。

## 原理

给定固定变量顺序，每个非终端节点测试一个变量，low/high 边分别代表 false/true；同构子图被
唯一表共享，等价函数被规约为同一结构。于是：

- `and/or/xor/not` 表示集合交/并/对称差/补集；
- `exist(varset)` 投影掉不关心字段；
- `replace(pairing)` 对 NAT、字段重命名等关系做变量替换；
- `isZero()` 判断约束是否不可满足；
- `satOne()` 提取一个反例/样例 flow 或 route。

```text
HeaderSpace / Routing constraints
 → bit-vector variables
 → BDD operations
 → canonical BDD
 → zero? 无解 : satOne() 构造具体反例
```

## 所有权和内存

BDD 对象背后引用 factory 节点。`xxxWith` 形式通常会消费/修改接收者或参数以减少临时引用；
`id()` 创建安全引用。错误复用被消费的 BDD 或遗漏释放会导致结果错误或节点表膨胀。修改调用
代码前必须阅读对应方法的 ownership 注释，不要根据方法名猜测。

所有参与同一运算的 BDD 必须来自同一个 `BDDFactory`。变量顺序显著影响图大小；新增报文字段
或 route 属性时应评估 ordering 和 node count，不只是功能正确性。

## 示例

```java
BDDFactory factory = JFactory.init(1_000_000, 100_000);
factory.setVarNum(2);

BDD x = factory.ithVar(0);
BDD y = factory.ithVar(1);
BDD exactlyOne = x.xor(y);

assert !exactlyOne.isZero();
BDD witness = exactlyOne.satOne();

witness.free();
exactlyOne.free();
x.free();
y.free();
factory.done();
```

仓库生产代码通常通过 `BDDPacket`、`BDDInteger`、transition 或 Minesweeper route abstraction
封装变量，不直接手工分配 index。

## Batfish 中的数据流

Packet 分析：

```text
Flow fields → BDDPacket → ACL/NAT/FIB Transition → StateExpr graph → reachable BDD → Flow
```

Route-policy 分析：

```text
prefix/metric/community/as-path → BDDRoute → TransferBDD → output constraints → witness route
```

`bdd` 只实现布尔引擎，不理解 ACL、flow、route 或 network state；这些语义分别在
`common/bdd`、`batfish/bddreachability` 和 `minesweeper`。

## 测试与性能

```bash
bazel test //projects/bdd/...
```

除真值正确性外，应检查：跨 factory 输入被拒绝、变量替换、量化、引用生命周期、hash/unique
table 扩容和极端节点数。性能回归可表现为相同答案但内存/时间指数增加，因此 BDD 变量布局
变化需用代表性大网络或专门 benchmark 验证。

## 修改注意事项

- 这是底层高风险模块；小改动可能影响所有 reachability 和 route-policy 问题。
- 保持规约/唯一表不变量；不要绕过 factory 创建节点。
- 明确 destructive 与 non-destructive API 的引用计数语义。
- 许可说明和上游来源在源码头及仓库 LICENSE 中，修改分发方式前需保留。
