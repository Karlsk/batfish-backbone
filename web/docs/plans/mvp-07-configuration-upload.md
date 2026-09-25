# MVP-07 配置上传实施计划

基线 MVP-06 已提交且真实环境累计120项通过。沿用100MiB接收、500MiB展开、5000条目、24小时TTL，配置字节原样保存。

- [x] 先建立 ZIP 路径/链接/加密/嵌套/重复/多根/实际展开限额、字节与摘要测试，再建立真实 PostgreSQL API/所有权/消费/清理测试。
- [x] API 在认证后解析 multipart，限定 files 或 archive 二选一，限制文件/字段及实际接收字节；解析临时文件总在退出时关闭。业务以有界流复制计数，不相信 Content-Length/ZIP 大小声明。
- [x] uploads 内部 archive 为 repository 的纯文件解析辅助，不跨模块调用；导入规则仅新增本模块 repository→archive→schemas，保留其他边界。原始文件用服务端文件ID写专属0700目录，manifest保留逻辑名、摘要、字节数、编码与行数；总摘要按排序路径+文件摘要计算。
- [x] UploadsService 仅通过 AuthService/NetworksService 验权和校验网络，repository 管理文件/ORM；DB flush后发布完整文件，再提交元数据；准备/flush失败清理，提交结果未知保留文件供引用对账；consume 锁行校验网络、所有者/管理员、过期及单次消费。
- [x] 过期未消费与孤立暂存清理提供运维CLI，不删除已消费文件；原始配置不进入错误与日志。
- [x] 真实HTTP用r1/r2多文件及Cisco ZIP上传；独立只读审查、累计回归、证据/文档与提交。

本篇不初始化快照。multipart 编码开销另设1MiB上限；原始文件内容仍严格受 UPLOAD_MAX_BYTES 限制。不能识别为UTF-8/GB18030的文件保留原始字节，manifest标记binary，后续查看不假定可解码。ZIP可选目录保留为普通文件，不执行。
