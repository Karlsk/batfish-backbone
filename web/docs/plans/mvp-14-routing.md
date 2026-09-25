# MVP-14 实施计划

基线 dedcc1a004。开放 routes/lpm-routes 专用接口，复用MVP-13已验证的异步分析、错误状态与结果管道。

1. 测试先行：两套真实配置逐行SDK对照，Cisco派生配置增加默认路由/BLUE VRF/丢弃路由，验证同前缀不同协议、前缀匹配方式和BGP空结果；下一跳SDK对象四种结构；IPv6/未知RIB拒绝。
2. 类型模型：nodes复用显式选择器，vrfs同形状但expression语义为Java正则（不是nodeSpec）；network/ip只接受IPv4；protocols为公开模板支持协议白名单列表；prefix_match_type严格模板四枚举，默认EXACT；routes rib main/bgp，LPM不开放rib。
3. 固定controller登记两个SDK问题；参数下推，结构化下一跳和VRF保留；LPM不虚构Next_Hop，详情由命中Node/VRF/Network查询routes。
4. JobsService增加受lease保护的内部运行阶段更新；AnalysisService经service更新cache-check/data-plane-or-query阶段，不声称引擎提供百分比或可判断数据面缓存命中。
5. 正式HTTP/CLI worker冒烟加入路由与LPM，两套配置保留全链路；一位只读审查者，累计回归与文档证据通过后提交，继续MVP-15。
