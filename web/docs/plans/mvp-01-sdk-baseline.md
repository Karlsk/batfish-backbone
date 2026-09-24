# MVP-01 实施与验证计划

日期：2026-09-25。执行依据：[MVP-01](../changeloge/mvp/mvp-01-sdk-compatibility.md)。本文件是该 spec 的实施清单，不是新增功能 spec。

目标：通过当前分支真实引擎，固定 SDK 版本与调用契约；不创建 Web API、前端或应用骨架，不自动提交。

实现方式：本会话使用 Superpowers writing-plans / executing-plans 方法按清单执行。测试直接调用公开 SDK，使用独立测试引擎、随机网络名和合成 Huawei/H3C 配置；结构化证据与结论分开保存。

## 交付与检查

- [x] `web/backend/tests/integration/test_sdk_baseline.py`：实际引擎版本/模板、节点/接口/路由/LPM/路径、初始化诊断、双 Session、缺失能力、公开任务查询与已有答案恢复。
- [x] `web/backend/tests/fixtures/small_network/`：两台合成路由器，已知静态路由与两跳路径；测试中派生另一快照和告警输入，避免接触真实配置。
- [x] 测试必须显式提供隔离引擎 host/port、唯一网络前缀及构建清单；缺少环境应失败而非跳过。证据记录运行版本、模板参数、结果 schema、类型与耗时。
- [x] 先尝试 spec 候选 Pybatfish 0.36.0；安装失败已观察到无该发行版。改测固定发行版 2026.9.17.3748，pytest 8.4.2，Python 3.12。
- [x] 在独立本机端口与临时存储启动本分支 JAR，运行针对性 pytest；负例覆盖未知问题/参数、缺失快照、重复初始化不覆盖、缺环境配置。
- [x] 检查 SDK 源码与实际行为：请求超时是否为作业时限、初始化返回值、后台问题句柄、重新建立 Session 后的状态/答案读取；没有证据的恢复/取消能力不承诺。
- [x] 回写 `sdk-compatibility.md`、能力覆盖表、运行基线、本篇和索引；关闭本次启动的测试引擎。全部必需项通过才标已完成。

重点：环境缺失不能假绿；同名显示标签不参与 SDK 路由；experimental 模板必须从引擎加载；SDK 对象与原始 JSON 要分别记录；失败/超时不能被解释为远端已停止。暂不运行全量 Java 测试，Java 源码没有改动。
