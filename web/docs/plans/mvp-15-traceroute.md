# MVP-15 实施计划

基线2fd851c926。复用已验证的异步分析和结构化Flow/Trace存储。

1. 测试先行：必要参数、IPv4、协议端口组合、严格布尔与max_traces边界；两套配置逐Flow/Trace与SDK对照；Cisco ECMP派生拒绝分支、成功/NO_ROUTE、maxTraces截断与ignore_filters；无可推导源地址的明确错误和随后显式source_ip恢复。
2. 增加traceroute请求模型和固定controller HeaderConstraints映射；默认ICMP/max_traces=5/ignore_filters=false，不选择管理地址代替SDK推导。
3. 公共TraceFlow增加返回路径的disposition计数；结果摘要按已保存路径分组、明确计数范围、保留总路径数/返回数/覆盖与截断。混合结果不归并成全部成功。忽略ACL、单向模型推演限制放在摘要/警告中。
4. 已知终态失败才从公开工作状态里的错误类别生成脱敏源地址/起点提示；这不改变引擎占用判定，不向用户暴露底层异常或配置。
5. 正式HTTP/独立worker冒烟加入traceroute和Flow/Trace读取，累计回归、独立只读审查、证据通过后提交；下一篇MVP-16前端骨架。
