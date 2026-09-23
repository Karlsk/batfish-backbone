# 本地私有配置样本

`NJ_SCT_R1`（H3C）和 `NJ-SCT-R02`（Huawei）是含真实认证材料的终端采集文件。
这两个文件由 `.gitignore` 排除，不随公开仓库分发；不要使用 `git add -f` 提交。
原文件仅保留在本机，不转码、不清理分页符、不改写换行。

获得授权后，将文件放入本目录，再运行：

```bash
bazel test //projects/batfish/src/test/java/org/batfish/vendor/h3c/grammar:tests --test_output=errors
```

`H3cRawCaptureTest` 在对应文件不存在时通过 JUnit assumption 明确跳过该样本测试。
其余合成 grammar、normalizer、route-policy 和双节点路由测试照常执行。
本目录的可选 Bazel filegroup 在文件存在时将原始字节作为 classpath resource 加载。
文件存在但内容有误时仍会测试失败，不会通过跳过掩盖错误。

仅添加忽略规则或执行 `git rm --cached` 不能移除旧提交中的敏感内容。
公开推送前必须同时确认待推送分支的完整历史中不再包含这两个文件或其副本。
