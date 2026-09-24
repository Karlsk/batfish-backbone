# 本地私有配置样本

`NJ_SCT_R1`（H3C）和 `NJ-SCT-R02`（Huawei）是含真实认证材料的终端采集文件。
这两个文件由 `.gitignore` 排除，不随公开仓库分发；不要使用 `git add -f` 提交。
原文件仅保留在本机，不转码、不清理分页符、不改写换行。

获得授权后，将文件放入本目录，再运行：

```bash
bazel test //projects/batfish/src/test/java/org/batfish/vendor/h3c/grammar:tests --test_output=errors
bazel test //projects/batfish/src/test/java/org/batfish/vendor/huawei/grammar:tests --test_output=errors
```

H3C / Huawei 的 raw-capture 测试在对应文件不存在时通过 JUnit assumption 明确跳过该样本测试。
其余合成 grammar、normalizer、route-policy 和双节点路由测试照常执行。
本目录的可选 Bazel filegroup 在文件存在时将原始字节作为 classpath resource 加载。
文件存在但内容有误时仍会测试失败，不会通过跳过掩盖错误。

R2 的分页覆盖包含前导空格和 ANSI 光标回退，不能用 H3C 的清理规则预处理。
Huawei 测试直接使用此文件，经生产加载链路验证 263 个接口、57 个 VPN instance、
2 个 ISIS 进程、1 个 BGP stanza、27 个策略（51 个节点）、15 个 EVPN instance。
能力边界及手动 API 验证见[Huawei 开发说明](../development-guide/modules/huawei-vrp.md)。

仅添加忽略规则或执行 `git rm --cached` 不能移除旧提交中的敏感内容。
公开推送前必须同时确认待推送分支的完整历史中不再包含这两个文件或其副本。
