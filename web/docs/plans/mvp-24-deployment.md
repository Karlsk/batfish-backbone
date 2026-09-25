# MVP-24 部署实施计划

按 spec-dev 与 executing-plans 在当前批次原地实施；独立只读审查后才提交。

目标：固定依赖镜像、当前分支JAR和问题模板，在全新本机隔离目录复现同域HTTPS完整服务。

1. 先建立部署验收脚本：新项目/新持久卷，HTTPS登录改密、两配置上传初始化、nodes结果；记录各容器版本和仅代理映射端口。未有compose时应失败。
2. backend/Dockerfile按uv.lock安装Python3.12应用，非root只读代码；frontend/Dockerfile固定pnpm构建后放入Nginx。deploy/compose.yaml拆分PG、迁移、API、worker、当前JAR引擎与TLS代理；PG/SDK只在内部网络，入口默认回环18443。配置/证书由私有目录注入，数据库密码不得进源码或构建层。
3. deploy管理脚本准备受保护目录、固定引擎摘要及模板、证书与随机数据库密码。启动、一次性管理员初始化、停止保留卷、离线一致备份、到全新项目恢复分别提供实际入口。备份前停止入口/API/worker且确认无queued/running及unknown/busy；未知状态拒绝备份直到对账。同时备份PG、应用数据、引擎卷和版本清单。恢复不覆盖已有实例。
4. 验收脚本真实重启API验证任务/结果保留；在SDK在途杀死本测试worker，重新启动检测interrupted/unknown并拒绝新SDK工作；停止worker、重启本测试Batfish、记录管理员对账后恢复。备份后新项目恢复，验证登录/历史结果及原快照新分析。
5. 编写web/README.md与deployment-validation.md；累计全部后端、前端、浏览器与部署复验；审查固定镜像、卷权限、代理头、恢复不误删、证据秘密边界。全部通过后提交。

验收不触碰其他容器；项目名前缀bfw-，不发布共享/生产，不宣称高可用或100设备容量。保持api/service/controller和串行SDK边界。
