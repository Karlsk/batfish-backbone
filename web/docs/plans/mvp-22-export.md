# MVP-22 实施计划

基线6d8a79e489；21已提交、累计260/31/10通过。

1. 先测试保存结果的完整上下文、公式/Unicode/换行、路径CSV拒绝、权限与无SDK重算。
2. ResultsService授权读取不可变结果，export模块迭代编码JSON/CSV，API仅校验format和映射下载响应。文件名仅服务端UUID。沿用100MiB保存上限；CSV解析有界保存文件，响应逐行输出。
3. JSON为metadata+data，metadata完整保留ResultEnvelope；CSV首行表头record_type/metadata_json/data:<列>，第二行metadata保存JSON元数据，随后data行。结构化单元格用JSON；带UTF8 BOM、公式前缀转义，JSON原值不变。
4. 页面统一下载按钮、格式说明与失败反馈，固定result来源，路径仅JSON；OpenAPI同步。
5. 独立只读审查、真实两拓扑下载、全部累计门槛、证据与提交。
