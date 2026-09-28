# 手动测试上传包

按 [手动测试指南](../../manual-testing.md) 顺序上传。所有 ZIP 都以 `configs/` 为顶层目录；校验命令：`shasum -a 256 -c SHA256SUMS`。

- `r1-r2.zip`：复制 `web/backend/tests/fixtures/small_network/configs/` 的 2 份配置。
- `cisco-four-baseline.zip`：复制 `web/backend/tests/fixtures/cisco_four/configs/` 的 4 份配置。
- `cisco-four-candidate-c2-link-down.zip`：以上一份为基础，仅将 `c2.cfg` 中 `GigabitEthernet0/1` 的 `no shutdown` 改为 `shutdown`。
- `example-live-bgp-acl.zip`：复制仓库 `networks/example/live/configs/` 的 13 份配置，用于 BGP 与 ACL 页面。

ZIP 使用固定时间戳和文件顺序生成，便于复核；不含账号、密码或运行数据。候选快照只表达配置输入变化，不预设真实设备或模型一定产生某种路径结果。
