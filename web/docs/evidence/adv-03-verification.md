# ADV-03 BGP 模型状态与兼容性接口验收

日期：2026-09-26；基线提交：`fdf2bb443d`（ADV-02）。状态：ADV-03 及 MVP-01～25、ADV-01～03 累计门槛通过。

`POST S/analyses/bgp-sessions` 接受空对象（默认 status）和 `options.mode=compatibility`，只允许有类型的设备及远端设备选择器；controller 固定调用 `bgpSessionStatus` 或 `bgpSessionCompatibility`。结果保存 SDK 原始列、状态、本地/远端节点、接口、VRF、AS、地址及其余字段。结果常驻“模型推演、非实时健康”提醒；Huawei/H3C 输入另附 IPv6 BGP 未建模范围。空行不作正常会话解读。

真实测试用当前固定版本引擎与 Pybatfish。Cisco 四设备派生同 AS 会话及 c1→c2 远端 AS 错配，逐行对照直接 SDK 答案，断言精确 peer 的 `NOT_COMPATIBLE`/配置不兼容状态；验证设备/远端筛选及 mode 缓存分隔。Huawei/H3C 派生快照明确上传 IPv6 BGP peer 配置，检查厂商覆盖标记和未建模提示。只读审查最初发现 IPv6 样本没有 peer 配置，补充真实配置并通过目标及完整回归后关闭该发现。

| 检查 | 实际结果 |
| --- | --- |
| 后端完整 `lab.py verify` | 314 passed、0 skip；be7cc2908bf6/checks/9c7001bf67ce |
| 实际 HTTP/worker `lab.py smoke` | 12 passed；302为有意筛选；checks/c27df0d33bf8 |
| 前端单测、类型/构建、OpenAPI 生成一致性、格式 | 55 passed / 19 files；其余通过 |
| 两套配置浏览器全回归 | 16 passed、0 skip/failed/flaky；干净实验环境9ab34410fb11 |
| 新 HTTPS 部署、服务重启/失联对账、备份和新卷恢复 | 通过；deploy-adv03-batch/verification.json |
| 恢复后生产构建浅色/深色 | 各3项部署＋1项双用户验收，均0 skip/failed/flaky |
| Ruff、离线锁文件、Markdown链接、Git空白检查 | 通过 |

浏览器验收前曾在重复加载的实验环境出现一次创建网络弹窗迟滞；重建实验环境后仅执行 `seed` 又遇首次改密页。按文档先执行 smoke 完成改密，再从干净环境完整重跑16项通过。失败 trace 与凭证仅保留在忽略提交的 `.runtime` 目录，不进入仓库。

环境：Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`，JAR SHA-256 `0927de7c740bc72f999870e842605baad9a7cb6ea66e4b01fb9a6037bea00193`，Pybatfish `2026.9.17.3748`，Python `3.12.12`，迁移0008。模型精度/现场状态不在本篇验证范围；不宣称100台设备容量。

[机器证据与源码指纹](adv-03-verification.json)：`94d9e7a25d753950d232de1c8cc9c467b6cb444a2b064209d18b47f230ea2887`。
