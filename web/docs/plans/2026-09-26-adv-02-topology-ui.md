# ADV-02 可交互拓扑实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将ADV-01保存的关系图变为可聚焦、有证据且可用键盘操作的拓扑视图。
**Architecture:** TopologyPage提供最小表单，TopologyForm复用现有任务/幂等/草稿流程；GraphResult仅按保存结果id读取图。Cytoscape负责展示与布局，设备/边列表和详情抽屉提供同等操作。来源绑定结果上下文，旧快照响应不能覆盖新结果。
**Tech Stack:** React/Ant Design/TanStack Query，新增锁定的Cytoscape.js及类型；生命周期参考[官方文档](https://js.cytoscape.org/#cy.destroy)。
**Spec:** [ADV-02](../changeloge/advance/adv-02-topology-ui.md)。必须在ADV-01累计验收及提交后开始实现。

## Global Constraints

- 消费已保存graph，不由前端推导邻接。默认首个设备与一跳邻居，最多200可见节点/边；选择列表受限时允许输入完整设备名聚焦。
- layer3/bgp/ospf/isis视图通过专用POST产生新任务/结果；高级节点/邻居条件使用现有typed selector。
- 显示实际来源、当前读取范围、模型限制与截断。协议关系不表示实时会话/链路通断。
- 图拖动仅改变布局，页面离开销毁实例；深浅主题均可读，列表按钮可键盘操作。

## Review Focus

- 快照/结果切换、慢响应迟到：组件key及完整queryKey隔离，旧图不能回填。
- 孤立节点、双向/多接口边、长设备名：保留后端ID，用节点/边前缀避免Cytoscape全局ID冲突。
- 超限、空图、焦点404、加载错误：可区分，不把失败解释为空图。
- 从固定结果进入路由查询：先按结果网络/快照恢复有效选择，再带入字面设备名；失效资源/草稿拒绝不导航。
- 重复提交与网络结果未知：保持原请求及幂等键；明确拒绝后允许修改重试。

## Task 1：图组件、数据边界与结果读取

- [x] 编写topology.test.tsx：稳定元素、重复边/孤立/长名称/200上限、实例销毁及旧响应隔离；先RED。
- [x] 新建features/topology/model.ts、GraphCanvas.tsx、GraphResult.tsx，默认聚焦一跳，按需详情与键盘替代列表。
- [x] ResultsPage接入kind=graph，复用来源、警告、导出；测试GREEN。

## Task 2：最小表单与上下文联动

- [x] 新增TopologyPage/TopologyForm和导航入口，视图选择常驻、专家参数折叠，提交后进入既有任务详情。
- [x] 结果侧支持同来源重新选择关系视图；节点详情提供接口证据与设备路由入口。
- [x] AnalysisPage仅对匹配当前network/snapshot的预填设备生效；测试上下文与草稿保护。

## Task 3：真实浏览器与累计提交门槛

- [x] 两套配置上传初始化→三层图→聚焦节点/接口详情→路由入口；空协议视图保留节点；双主题和键盘/图拖动检查。
- [x] 一个只读审查；执行全部后端/前端/浏览器/双用户与本机部署恢复累计门槛。
- [x] 回写spec/索引/矩阵/源码证据，提交后继续ADV-03，不另行询问。

实施及累计验证完成：见 [ADV-02验收](../evidence/adv-02-verification.md)。
