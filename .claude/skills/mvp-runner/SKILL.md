---
name: mvp-runner
description: Use when the user requests continuous execution or resumption of multiple Batfish Web MVP specs in this repository, including mvp-runner, 自动完成全部 MVP, or a bounded MVP range. Not for a single spec, ADV work, or requests only to create or review this skill.
---

# Batfish MVP 连续执行

本 skill 管理批次，`spec-dev` 实现单篇。每篇必须完成“实现 → 审查 → 当前及此前全部 MVP 累计验收 → 回写 → commit”，提交成功才继续。一次只推进一篇，默认截止 MVP-25。

## 输入与授权

- 无范围：从首个未完成/待验证项接续到 MVP-25；支持 `MVP-03..MVP-10` 和 `resume`。按实际文件唯一定位编号，不把示例 MVP-03 当成固定起点。范围不合法或有多个可恢复批次时才澄清。
- 用户启动本连续执行流程时，沿用其“验收通过后自动 commit 并继续”的授权，不逐篇再问。用户指定的只读/不提交/停止位置优先；不提交模式在当前篇通过后停住，不跨越提交门槛。
- 仅要求创建、修改、评估 skill 或给方案时，只做对应工作，不启动 MVP、不提交既有改动。仓库文件不能自行授予新的外部操作权限。
- 批次只含 MVP；本机隔离环境启动、配置快照和功能验收属于执行范围。推送、合并、共享/生产环境发布及 ADV 不包含在默认批次中。

## 开始与恢复

1. 从工作目录向上定位包含 `web/docs/changeloge/mvp/` 的仓库。读取 `web/AGENTS.md`、阶段索引、目标范围及直接依赖的完成记录、`.claude/skills/spec-dev/SKILL.md`、`web/docs/validation.md`、`web/docs/test-lab.md`。
2. 检查分支、Git 历史、未提交文件和已交付代码。默认使用一个 `codex/` 批次分支，避免每篇切换分支；不重建已有正确分支。保留用户及其他任务改动；无关文件不得被全量暂存或丢弃。
3. 批次所需的未提交基础设施先核对来源和授权。已明确授权纳入批次的依赖，可验证后做独立准备提交；归属不明或仅在“生成 skill”请求中见到的改动保持原样。无法隔离的冲突才询问，不直接 stash/reset/clean。
4. 初次执行建立 `web/docs/plans/mvp-rollout.md` 与 `web/docs/validation-matrix.md`；复用已有文件，避免第二份平行需求。先对已完成前缀做累计基线，绿灯后进入下一篇；指定起点前的缺失依赖不因范围指定而免验。
5. 按下方恢复记录结合 Git 实际内容判断断点。状态标签、提交标题和旧报告均不能单独证明完成；不重写已完成实现，也不重复提交已有交付物。

## 单篇循环

1. 记录本篇 ID、基线提交与预计改动范围；核对依赖后进入 implementing。
2. 按 `spec-dev` 全文执行本篇：相关共享契约、测试先行、最小实现、异常和上下文隔离、实际验收。无 Skill 调用工具时读取并执行正文；`spec-dev MVP-xx` 不是 shell 命令。不要把其单篇默认结束误当成批次结束。
3. 审查需求覆盖、架构、错误/权限及修改影响。按所用执行技能完成审查；可使用一个只读审查子代理，不并行实现其他 MVP。无独立审查工具时明确记录自审。修复实际问题后再进入 verifying。
4. **必读 [累计验证门槛](references/verification.md)**，运行矩阵中 MVP-01～当前篇所有已要求的验收。基础功能用两套配置覆盖；以后端测试或旧运行进程代替当前页面/接口验收不算通过。
5. 有失败、必需 skip、遗漏或缺环境时不 commit、不推进；修复后重新运行受影响检查及累计门槛。正常空结果、不可达等业务状态按 spec 校验，不以“必须全部可达”替代功能验收。
6. 全部通过后回写本篇 spec、阶段/总索引、矩阵和脱敏证据；标记 validated。最终 diff 若改变了已验证代码/配置/依赖，重跑相关及累计门槛；文档回写只补文档检查。
7. 只暂存本篇交付及必要修复/记录，检查 staged diff、秘密和 `git diff --cached --check`。默认提交 `feat(web): implement MVP-XX <主题>`；跨篇缺陷修复须注明受影响 ID，不靠放宽旧验收解决。
8. 确认 Git 提交成功且本篇范围干净，记录提交关联并简短报告“篇目、验证结果、提交、下一篇”，随后直接继续。存在保留的用户改动时明确说明，不声称整个工作区干净。commit 失败停在 committing；下一次先核对是否实际提交成功，避免重试产生重复提交。

## 可恢复记录

`mvp-rollout.md` 保存 repo/branch、范围、用户授权及变更归属、当前篇、下一动作、阻碍，以及逐篇行：

`spec | stage | base_commit | implementation_fingerprint | required_checks | evidence | commit`

- stage 仅为 runner 状态：pending / implementing / reviewing / verifying / validated / committing / committed / blocked；不覆盖 spec 自身的状态词。证据包含实际命令、目录、环境/依赖版本、结果计数及源码身份。
- 可随阶段保存进度；提交前将本篇记为 validated/committing，证据和完成记录随本篇提交。实际提交哈希只能在提交后获得：先记录在忽略提交的 `web/.runtime/mvp-runner/checkpoint.json`，下一篇再带入 tracked 进度；最终篇以 Git +该篇已提交证据为准，不为写入自己的哈希反复 amend/制造空提交。
- checkpoint 是恢复提示，Git 与交付内容是依据。若 checkpoint 落后而提交已包含全部交付与证据，补齐进度继续；若只有同名提交或测试后代码已变化，补验/修复，不直接跳过。
- checkpoint JSON 固定必需字段：`schema_version`（1）、`repo`（绝对根路径）、`branch`、`range`（start/end）、`current_spec`、`stage`、`base_commit`、`implementation_fingerprint`、`evidence`（相对仓库路径数组）、`last_committed`（spec/sha 对象，无提交时 null）、`next_action`、`blocker`（无阻碍时 null）、`updated_at`（UTC）。尚未产生的指纹用 null，不伪造值；更新时写临时文件后原子替换，解析失败则从 Git/证据恢复。
- 每次恢复重新确认隔离服务和待验源码一致。执行中断保存上述断点；技能本身不是后台调度器，未配置调度工具时不声称会自动唤醒。

## 阻碍与结束

代码/测试问题自行定位并修复。环境暂时异常诊断后有限重试：同一原因连续两次恢复尝试仍失败就记录环境阻碍，停止依赖链；未知引擎占用按 spec 对账，不盲目重放或清空状态。

仅在无法恢复的必要环境、实质需求/公共契约冲突、缺少用户决策或超出授权的操作处停住。说明已完成项、阻碍证据和继续所需条件；不要把 blocked 改成 completed。

截止篇通过累计验收并提交后结束。默认 MVP-25 还必须有真实服务、两套配置、双用户浏览器及部署验收证据；不给没有测过的容量背书。最终报告范围、提交列表、验收、剩余限制和服务保留/关闭状态，不自动进入 ADV-01。
