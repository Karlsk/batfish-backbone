# ADV-01 拓扑接口实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为已确认 ADV-01 提供可追溯、可筛选的三层及协议关系图。
**Architecture:** 沿用 api/service/controller；一个任务一个Session，顺序执行节点清单与边问题。公共Graph DTO持久化于结果文件，读取只经过ResultsService，不调用SDK。
**Tech Stack:** 现有FastAPI/Pydantic/PostgreSQL/Pybatfish，不增加依赖或数据库迁移。
**Spec:** [ADV-01](../changeloge/advance/adv-01-topology-api.md)。前置MVP全验收已提交 b59995435c。

## Global Constraints

- view仅layer3/bgp/ospf/isis，默认layer3；options仅typed nodes/remote_nodes。
- 节点清单为两侧选择集合的并集，任一侧未限制即包括全部节点，保留孤立节点。
- 边保持方向与接口/IP/AS原始证据，稳定ID不可将反向或并行边合并。
- GET默认limit=200、hops=1，hops允许0～5；未给focus时忽略hops，给focus时按无向邻接找邻域但输出保留原有向边。不存在的focus返回404。
- limit分别约束节点和边；focus优先、距离优先、ID稳定排序；节点/边不足标truncated，永不返回悬空边。计算过滤与读取范围分别记录。
- 协议关系不代表会话健康；没有边不代表物理断线。不开发ADV-02图形页面。

## Review Focus

- 两个相同端点的不同接口/BGP peer必须有不同ID，测试双向/并行关系。
- 空协议图仍返回节点，测试isolated与实际空协议视图。
- 图裁剪及字节限制不得留下悬空边，测试节点/边/字节上限。
- 错误选择表达式终态释放占用；未知超时保持栅栏，保留现有controller回归。
- 任意SDK方法/上下文不能透传；API和service都验证typed白名单，测试非法view/options及图kind冲突。

## Task 1: 参数与SDK图归一化

- [x] tests/test_topology.py先测试Registry登记与非法参数，验证失败。
- [x] 新建analysis/schemas/topology.py与controllers/topology.py；固定问题映射、节点/边Graph DTO。
- [x] 抽取controller内部同Session问答函数，保留后台轮询、确定失败释放、未知失败栅栏。
- [x] 测试稳定边ID、原始属性、孤立节点与选择参数映射。

## Task 2: 保存与读取

- [x] 先补邻域/数量/字节限制失败测试。
- [x] 新建results/graph.py，publish支持graph；新增ResultsService.graph及只负责校验的GET API。
- [x] POST topology接现有权限、幂等、队列、缓存、结果发布链；更新公共契约与生成类型。

## Task 3: 真实SDK验收及累计回归

- [x] r1/r2、Cisco四设备四视图逐行原始SDK对照；派生Cisco配置启用BGP/ISIS确保非空，单独孤立节点样例。
- [x] 验证API默认值、过滤、读取范围、导出、权限/参数失败与缓存；执行lab.py verify累计后端、smoke与前端全部现有检查。
- [x] 只读独立审查、修复阻断项，回写spec/阶段索引/实际证据；本篇不自动进入ADV-02或自动提交。

## 完成记录

全部实施与验收项已完成。后端307、冒烟12、前端47、浏览器14通过，详见[验收报告](../evidence/adv-01-verification.md)。独立审查契约遗漏已补齐，无延期项；本篇按spec-dev默认保留未提交。
