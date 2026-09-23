# question 模块

## 职责

[`projects/question`](../../../projects/question) 实现 Batfish 标准问题。每个问题把类型化输入
映射为对 VI 配置、拓扑、dataplane 或 traceroute engine 的读取，再生成 `AnswerElement`。
问题不负责 HTTP、排队、解析厂商配置或持久化。

## 三层模型

```text
questions/stable/foo.json
  instanceName + variables + class
          |
          v
FooQuestion extends Question
  JSON properties + getDataPlane()/getDifferential()
          |
          v
FooQuestionPlugin extends QuestionPlugin
  createQuestion() + createAnswerer()
          |
          v
FooAnswerer extends Answerer
  IBatfish → model/dataplane → AnswerElement
```

公共基类分别位于：

- [`Question`](../../../projects/common/src/main/java/org/batfish/datamodel/questions/Question.java)
- [`QuestionPlugin`](../../../projects/question/src/main/java/org/batfish/question/QuestionPlugin.java)
- [`Answerer`](../../../projects/common/src/main/java/org/batfish/common/Answerer.java)
- [`IBatfish`](../../../projects/common/src/main/java/org/batfish/common/plugin/IBatfish.java)

## 实现原理：插件发现与执行

插件类使用 `@AutoService(Plugin.class)`，构建时生成 service metadata；`allinone` 必须把 question
模块放在 runtime classpath，`PluginConsumer` 才能发现。插件的 question 名称与 JSON template
`instanceName` 不必相同；多个模板可以复用同一个 Java Question。

例如 [`bgpRib.json`](../../../questions/stable/bgpRib.json) 和
[`routes.json`](../../../questions/stable/routes.json) 都引用 routes 实现，但设置不同参数/展示。

## Answerer 数据流

```text
Question JSON 反序列化
 → Batfish 根据 getDataPlane() 预热配置/dataplane
 → plugin.createAnswerer(question, ibatfish)
 → answer(snapshot)
    ├─ SpecifierFactories 解析 nodes/interfaces/filters
    ├─ IBatfish.loadConfigurations/loadDataPlane/...
    ├─ 计算 Row 或领域 answer 对象
    └─ TableAnswerElement.postProcessAnswer(question, rows)
 → Answer 包装 metadata/status
```

表格问题需先定义 `TableMetadata`：列名、Schema、描述和 key/value 属性。列定义是外部 API；
Pybatfish DataFrame、过滤和用户脚本都可能依赖名称与类型。

## 示例：IpOwners 的结构

参考：

- [`IpOwnersQuestionPlugin`](../../../projects/question/src/main/java/org/batfish/question/ipowners/IpOwnersQuestionPlugin.java)
- [`IpOwnersQuestion`](../../../projects/question/src/main/java/org/batfish/question/ipowners/IpOwnersQuestion.java)
- [`IpOwnersAnswerer`](../../../projects/question/src/main/java/org/batfish/question/ipowners/IpOwnersAnswerer.java)
- [`IpOwnersAnswererTest`](../../../projects/question/src/test/java/org/batfish/question/ipowners/IpOwnersAnswererTest.java)

`Question` 保存输入 IP specifier；`Answerer` 从 `IBatfish` 获取 snapshot 的 IP owners，把每个 IP、
node、VRF、interface、active 状态变成 row。该问题不需要 dataplane，因此不会为简单属性查询
触发昂贵计算。

## 新问题骨架

```java
@AutoService(Plugin.class)
public final class AcmeQuestionPlugin extends QuestionPlugin {
  @Override
  protected Answerer createAnswerer(Question question, IBatfish batfish) {
    return new AcmeAnswerer((AcmeQuestion) question, batfish);
  }

  @Override
  protected Question createQuestion() {
    return new AcmeQuestion();
  }
}
```

```java
public final class AcmeAnswerer extends Answerer {
  public AcmeAnswerer(AcmeQuestion question, IBatfish batfish) {
    super(question, batfish);
  }

  @Override
  public AnswerElement answer(NetworkSnapshot snapshot) {
    SortedMap<String, Configuration> configs = _batfish.loadConfigurations(snapshot);
    TableAnswerElement table = new TableAnswerElement(metadata());
    table.postProcessAnswer(_question, rows(configs));
    return table;
  }
}
```

还需添加 JSON template、BUILD target/deps、Question JSON round-trip test、Answerer 行为测试与用户
文档。完整流程见 [`docs/question_development`](../../question_development/README.md) 和
[`writing_custom_questions`](../../tutorials/writing_custom_questions.md)。

## 问题分类

- 配置属性：node/interface/OSPF/BGP process 属性，通常不需 dataplane。
- 初始化质量：parse status/warning、conversion status/warning、defined/reference structures。
- 拓扑/会话：edges、BGP/OSPF/IPsec session status。
- 路由：routes、BGP/EVPN RIB、LPM。
- 转发：traceroute、reachability、loop、bidirectional/differential reachability。
- 策略：test/search filters、route policies、filter-line reachability。

是否需要 dataplane 必须准确声明。误设 `true` 会产生不必要的分钟级计算；误设 `false` 可能让
Answerer 在缺失状态下失败或读到不完整模型。

## 测试

```bash
bazel test //projects/question/...

# 单个问题包
bazel test //projects/question/src/test/java/org/batfish/question/ipowners/...
```

测试重点：空输入、specifier 无匹配、多个 VRF/节点、排序、nullable 字段、列 schema、差异模式、
dataplane 声明以及 warning/exception。避免只对字符串化表格做断言，优先断言 row 和领域值。

## 修改注意事项

- Answerer 只读模型；不要修改 cached `Configuration`/`DataPlane`。
- 输出列改名/类型变化是 API 变更，需同步 Pybatfish 文档与消费者。
- 厂商专有逻辑应在 conversion 归一化，而不是在问题中 switch vendor。
- 对大网络先通过 specifier 缩小输入，避免构造全量 rows 后再过滤。
