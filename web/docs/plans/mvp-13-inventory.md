# MVP-13 实施计划

基线：50cbc1d307；范围：设备/接口两类专用分析，沿用已有共享任务和结果管道。

1. 先写参数校验、特殊字面名称、SDK 对照、正常空结果及真实 HTTP/worker 冒烟用例，确认缺少功能时失败。
2. schemas 改为包，增加 inventory 类型：nodes 的筛选在 options，interfaces 的 nodes 是可选顶层参数。选择器显式 mode=literal + values 或 mode=expression + expression；缺省选择全部。properties 是固定引擎支持属性的有界白名单列表，默认精简列。
3. controller 把字面名称编码成锚定的 Java 正则，每字符使用十六进制码点，避免引号、逗号、方括号、斜线等变成表达式；专家表达式原样交给 SDK。登记固定 nodeProperties/interfaceProperties 调用，不反射方法名。
4. API 校验类型、身份和幂等键；service 复用快照状态、版本核验、任务、缓存、结果发布。空表返回成功与明确说明；模型覆盖警告保留。
5. 两套真实配置检查稳定列/直接 SDK 相等；特殊名称单独合成配置验证。替换 MVP-12 的测试专用冒烟登记为真实产品路由与独立 CLI worker。
6. 一次只读独立审查，修复后累计 MVP-01～13 验证、Ruff/锁文件/文档检查，更新证据后提交并继续 MVP-14。
