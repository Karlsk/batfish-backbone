# MVP 连续实施记录

开始日期：2026-09-25。仓库：`/Users/gaorenjie/Documents/Coding/JAVA/batfish-dev`。分支：`codex/mvp-integration-lab`。批次基线：`c8d826dcf1`。

用户已启动 mvp-runner：先检查 MVP-01/02，再从首个未完成项连续实施到 MVP-25。每篇实现、审查、当前及此前全部 MVP 累计验收通过后提交并继续；不推送、不进入 ADV、不发布到共享/生产环境。启动时工作区干净，测试环境和 runner 已分别提交，不存在混入用户改动的问题。

## 当前进度

- 当前阶段：MVP-18 validated；后端260/前端16/浏览器5通过，0skip。
- 下一动作：提交 MVP-18，继续 MVP-19 任务中心与解析诊断。
- 环境观察：旧 API/JVM 已停止，保留了上一轮临时 PostgreSQL 容器；核对运行清单/标签后只停止该容器，重建测试环境。没有把历史证据当作本轮通过。
- 当前无需求决策阻碍。所有新证据记录实际源码身份，运行凭证和完整日志留在忽略提交的 `.runtime/`。

| spec | stage | base_commit | implementation_fingerprint | required_checks | evidence | commit |
| --- | --- | --- | --- | --- | --- | --- |
| MVP-01 | committed（本轮复验通过） | c8d826dcf1 | [基线证据](../evidence/mvp-prefix-recheck.json) | SDK 基线、两套配置 | [基线证据](../evidence/mvp-prefix-recheck.json) | a255fc3759 |
| MVP-02 | committed（本轮复验通过） | c8d826dcf1 | [基线证据](../evidence/mvp-prefix-recheck.json) | 健康/错误/DTO/分层、HTTP、SDK 回归 | [基线证据](../evidence/mvp-prefix-recheck.json) | fcfbbc04f0 |
| MVP-03 | committed | c8d826dcf1 | 7bb3e8545628972002d041f26f1553d445a066bb9520eaeb53c6dceacfea5b4d | 累计 87 passed；Ruff/锁文件/文档通过 | [验收](../evidence/mvp-03-verification.json) | 28ee717b90 |
| MVP-04 | committed | 28ee717b90 | 627a4000e80ed11ddf2171a66db2e296fc66e8bd05b661a6b761249ab099fbb6 | 累计 98 passed；Ruff/锁文件/文档通过 | [验收](../evidence/mvp-04-verification.json) | 6047cae771 |
| MVP-05 | committed | 6047cae771 | f105a36b8d4f67411235fd6e433961633487fc0b0c374b8c0a9a53f0979e3554 | 累计 107 passed；Ruff/锁文件/文档通过 | [验收](../evidence/mvp-05-verification.json) | 46c17db185 |
| MVP-06 | committed | 46c17db185 | ad5bd5a8cdabd8d38bb372e27a275f44ddbedc81581ccaa75aa4914008e530f3 | 累计 120 passed；Ruff/锁文件/文档通过 | [验收](../evidence/mvp-06-verification.json) | 8cce94561d |
| MVP-07 | committed | 8cce94561d | 508d2eeb8a2fd6f2a4aebb2a013534fc978636f7274213102615ab3d966faa43 | 累计159 passed；smoke8；Ruff/锁文件/文档通过 | [验收](../evidence/mvp-07-verification.json) | 9c2b3f94fa |
| MVP-08 | committed | 9c2b3f94fa | 091e14cf6d996169c80307635d8adc49b3d9dff12c82d9db47e20137cb687e27 | 累计170 passed；smoke9；Ruff/锁文件/文档通过 | [验收](../evidence/mvp-08-verification.json) | c4c2b7ac4f |
| MVP-09 | committed | c4c2b7ac4f | 2cff73fe4b9bc477d5fd01da80ab1650aaeb1bd51cc8a54e33688701e31e0cf6 | 累计189 passed；smoke10；Ruff/锁文件/文档通过 | [验收](../evidence/mvp-09-verification.json) | ca8188def4 |
| MVP-10 | committed | ca8188def4 | d247aa78e52bf656de3bcd934bb3b0c86b8561f54daca4e17b3982185835ff8c | 累计201 passed；smoke12；Ruff/锁文件/文档通过 | [验收](../evidence/mvp-10-verification.json) | 2cae778757 |
| MVP-11 | committed | 2cae778757 | 70f5482c8aa4b3bde5e6f25c2776764cd90bacca84705c7a764ce18835a5069c | 累计218 passed；smoke12；Ruff/锁文件/文档通过 | [验收](../evidence/mvp-11-verification.json) | 95df112c1e |
| MVP-12 | committed | 95df112c1e | f211ce5c9909f423dec3eef3a60234c572e0837c93291c276039fef0829f3a03 | 累计231 passed；smoke12；Ruff/锁文件/文档通过 | [验收](../evidence/mvp-12-verification.json) | 50cbc1d307 |
| MVP-13 | committed | 50cbc1d307 | 42f94d1c760982615c7dc0a1e6243bb020f5f68006dd4830a88b3c42b90cbac0 | 累计246 passed；smoke12；Ruff/锁文件/文档通过 | [验收](../evidence/mvp-13-verification.json) | dedcc1a004 |
| MVP-14 | committed | dedcc1a004 | 624aaefdfdcd3cf3239eb5e0ee236997c5bcd96099427e716204593c56f018f4 | 累计252 passed；smoke12；Ruff/锁文件/文档通过 | [验收](../evidence/mvp-14-verification.json) | 2fd851c926 |
| MVP-15 | committed | 2fd851c926 | e7ad202de43ece28d8aa3e594b9931f8f020d3ef220903b30a1318e2c9b9625e | 累计259 passed；smoke12；Ruff/锁文件/文档通过 | [验收](../evidence/mvp-15-verification.json) | 42f7aea7f5 |
| MVP-16 | committed | 42f7aea7f5 | d4290535f64042740d1e4da7e7089c90121faf770185ed9caaa774a7ff0d6895 | 后端259/前端7/浏览器2；smoke12；静态检查通过 | [验收](../evidence/mvp-16-verification.json) | d0b0e47691 |
| MVP-17 | committed | d0b0e47691 | 9b21ecbd608dd0175194c99b14c1a84f26e25e28325ea92799a7447f06b99113 | 后端259/前端12/浏览器3；smoke12；静态检查通过 | [验收](../evidence/mvp-17-verification.json) | e4b00ccdb3 |
| MVP-18 | validated | e4b00ccdb3 | 53f43e6fccfc1025862ecf69976546227dd1456fe21661ce246eaadcdac433a4 | 后端260/前端16/浏览器5；smoke12；静态检查通过 | [验收](../evidence/mvp-18-verification.json) | 待提交 |
| MVP-19～25 | pending | 各篇开工时记录 | 尚未生成 | 逐篇加入验收矩阵 | 尚未运行 | 尚未提交 |

可恢复状态：`web/.runtime/mvp-runner/checkpoint.json`。提交后的实际哈希先写 checkpoint，下一篇带入本文件；不为记录自己的哈希重复提交。

## 执行约束

沿用现有 spec 与共享契约，不生成平行需求；按 writing-plans / executing-plans / TDD 方法逐篇推进。本篇所需表、测试及最小基础设施可建立，后续业务行为留给所属 spec。每篇使用一个只读审查者，主流程串行实现。

使用实际本机 Batfish、PostgreSQL、API 与逐步实现的 worker/前端；设备仅使用配置。运行旧代码的服务必须刷新，数据库环境重建后重新迁移并 seed。已有前端/浏览器/部署验证不能被后端 pytest 代替。失败修复后复验，不降低验收标准。
