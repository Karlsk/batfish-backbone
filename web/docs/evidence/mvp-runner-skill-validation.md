# mvp-runner 技能验证记录

日期：2026-09-25。范围：创建项目级 runner、接入单篇 spec-dev 与项目规范、验证技能结构及场景决策。**本次没有启动 MVP 连续执行、运行新的产品验收或提交当前改动。**

## 交付

- [mvp-runner 正文](../../../.claude/skills/mvp-runner/SKILL.md) 与 [累计验证门槛](../../../.claude/skills/mvp-runner/references/verification.md)。
- `.claude/skills/mvp-runner/agents/openai.yaml`：项目技能 UI 元数据，保留默认自动发现。
- `.agents/skills/mvp-runner`：指向上述目录的相对符号链接，与既有项目布局一致。
- `spec-dev` 明确只承担当前篇，授权后的累计验收/提交/继续交给 runner；`web/AGENTS.md` 明确批次授权例外及配置测试边界；[开发流程](../development-workflow.md) 补充启动、范围和恢复用法。

## 结构验证

在仓库根目录使用已存在的 `web/backend/.venv/bin/python`：

```text
python <skill-creator>/scripts/quick_validate.py .claude/skills/mvp-runner
python <skill-creator>/scripts/quick_validate.py .claude/skills/spec-dev
```

实际 `<skill-creator>` 为 `/Users/gaorenjie/.codex/skills/.system/skill-creator`。两项均输出 `Skill is valid!`。另行解析 YAML，验证 UI 描述长度、提示词包含 `$mvp-runner`、未禁用默认发现；相对链接解析到唯一实体；正文/参考/流程文档的本地链接及 `git diff --check` 通过。

确认没有创建 `web/docs/plans/mvp-rollout.md` 或 `.runtime/mvp-runner/checkpoint.json`，没有提前制造执行进度。上一轮测试环境改动保留，未暂存、未提交。

## 独立场景验证

先用既有 spec-dev、AGENTS 和测试环境说明做 5 个只读基线场景；独立代理在这些场景中已做出正确决定，未观察到可复现的无 skill 违规。因此不声称本次验证证明了某个 RED→GREEN 行为改善；新增 skill 是对用户已讨论流程的明确封装。

创建后由另一个独立代理读取新 skill 及验证参考，执行 7 个只读决策场景。代理未执行真实开发、服务操作或 Git 写入；结果如下：

| 场景 | 实际判断 |
| --- | --- |
| MVP-18 全绿摘要但 PostgreSQL 有 4 个 skip，时间紧 | 不提交/不推进；补真实数据库条件，运行缺项及全部累计验收 |
| checkpoint 停在 MVP-11，但存在同名提交，另有用户脏文件 | 检查提交内容、实现和证据；保护用户改动，避免重复提交；不只凭标题跳过 |
| MVP-06 已改 API，服务仍是 MVP-02 旧进程，health=200 | 拒绝以旧进程验收；刷新受控服务，必要时重新迁移/seed，再测当前接口 |
| 用户只要求生成 skill，前次实验代码尚未提交 | 只生成/验证 skill，不启动批次、不提交实验代码 |
| MVP-25 测试通过 | 核对完整矩阵、双用户页面、部署和两套配置证据，提交成功后结束，不进入 ADV |
| MVP-19 只运行 lab.py verify，遗漏前端/浏览器 | 不提交；从实际 scripts 补前端/构建/页面验收，不假称后端入口已统一覆盖 |
| 最后提交成功但 checkpoint 仍为 committing | 核对 Git/证据后更新运行时 checkpoint；不为嵌入自己的哈希重复 amend/创建空提交 |

7 个场景的决定符合既定流程。审查未发现阻塞项；提出 checkpoint 字段未固定的小项，已在正文明确 JSON 必需字段、空值和原子写入方式。后续 worker/前端/部署启动规则随所属 MVP 补齐，正文已要求逐篇更新验收矩阵和真实检查入口。

这些是有限的只读场景样本及结构检查，不等于已连续运行 23 篇 MVP，也不证明任意中断或未来测试环境都能无人干预恢复。实际批次仍以逐篇 Git、源码身份和执行证据为准。
