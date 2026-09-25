# MVP-24 部署验收

状态：通过。全新部署、SDK在途worker失联/对账、三卷一致备份、新项目空卷恢复、历史结果/新查询及HTTPS生产浏览器均通过。

入口为仓库根web/scripts/deploy.py与verify_deployment.py，完整步骤见[部署README](../README.md)。测试只管理本任务创建的bfw项目，失败实例停止并保留诊断，不控制其他容器。

构建固定Python镜像（实际3.12.13）、Node镜像（实际25.9.0）、uv0.11.2、pnpm11.19.0、SDK2026.9.17.3748、Postgres17和Java25JRE摘要。当前分支JAR的revision及SHA256与[兼容性基线](sdk-compatibility.md)一致，问题模板摘要随引擎镜像保存。

真实部署发现MVP-07/10的附带README初始化失败，已复用safe_path并新增合法附带文件/路径穿越回归。打包修正包含pnpm版本例外文件、共享镜像单次构建、无curl的Java镜像健康检查、Nginx全部临时目录tmpfs。备份前停止入口/API/worker并检查队列与引擎idle，同时保存数据库、应用及引擎卷；恢复到新项目并恢复UID10001。

恢复演练将worker在SDK请求等待时终止；unknown不可自动释放，重启worker后按60秒阈值扫描interrupted，停worker/重启受控引擎/管理员记录对账后才继续执行。

最终实例：`bfw-1fc2d1f6cf81`，运行证据保存在`web/.runtime/deploy-mvp24-release`。原实例备份后停止，恢复实例入口https://localhost:18444。完整脱敏结果、镜像ID/版本、源码指纹与检查计数见 [MVP-24证据](evidence/mvp-24-verification.json)。
