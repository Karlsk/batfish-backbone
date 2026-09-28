# 按 spec 推进 Batfish Web

采用项目专用 `spec-dev` 作为单篇开发入口，`mvp-runner` 管理连续批次（无参数仍只处理 MVP；新 CMDB/SIM 必须显式给范围）；Superpowers 提供按需计划、测试、调试和验证方法，`grill-me` 用于未决方案的交互澄清。MVP/ADV/LDR 已完成，新 CMDB/SIM 是待开发的需求与验收依据；本流程不初始化 Spec-Kit，不复制一套平行需求文件。

## 项目级安装布局

```text
.claude/skills/
├── spec-dev/             # 本项目专用
├── mvp-runner/           # 顺序开发、累计验收、逐篇提交及恢复
├── grill-me/             # 上游访谈入口
└── grilling/             # 上游访谈实现，grill-me 的依赖
.agents/skills/
├── spec-dev -> ../../.claude/skills/spec-dev
├── mvp-runner -> ../../.claude/skills/mvp-runner
├── grill-me -> ../../.claude/skills/grill-me
└── grilling -> ../../.claude/skills/grilling
web/
├── AGENTS.md             # 统一项目规范
└── CLAUDE.md             # 引用 AGENTS.md
```

`.claude/skills` 保存唯一实体，`.agents/skills` 使用相对符号链接供 Codex 发现。两种客户端读取同一份内容；不写入用户级技能目录，不修改原 Hify skill。项目规范使用标准大写 `AGENTS.md`，从仓库根目录启动的 `spec-dev` 也会显式读取它。

安装时当前会话已提供 Superpowers 6.4.1；本次没有复制或安装项目级 Superpowers。其他环境没有 Superpowers 时，`spec-dev` 仍可按自身流程工作，并明确说明哪些辅助技能未加载。

## 使用方法

在本仓库打开下一轮对话，使用客户端的 skill 选择器或直接描述“使用 spec-dev 执行 MVP-01”。支持 `$` 技能语法的 Codex 客户端可输入：

```text
$spec-dev MVP-01
```

Claude Code 可输入 `/spec-dev MVP-01`。也支持完整 spec 路径，例如：

```text
$spec-dev web/docs/changeloge/mvp/mvp-16-frontend-foundation.md
```

这些是发给智能体的指令，不是 shell 命令。MVP-16 示例仅展示路径格式；依赖未满足时会指出缺失项，不会越过前序验收。每篇完成后再调用下一篇；所有篇目和依赖见 [研发规格总索引](changeloge/README.md)。

需要探讨新方案时：

```text
$grill-me 请检查 ADV-09 的专家入口设计，每次只问一个关键问题，已在 web/docs 中确认的决策不重复询问。
```

Claude Code 对应 `/grill-me`。上游 `grill-me` 只负责调用 `grilling`；后者默认按依赖关系分轮提问，可以按用户要求改为一次一问。没有专用 Skill 工具的客户端，可明确要求“读取项目 .claude/skills/grill-me/SKILL.md 和 grilling/SKILL.md，按正文执行”。

访谈解决设计决策，`spec-dev` 执行已确认需求，不必在每篇前重复访谈。上游 `grilling` 要求共同理解得到用户确认再采取后续行动；已经明确确认的事项保留，不重问。技能应在安装后的下一轮可用；若客户端没有刷新，重新打开项目会话。

## 一篇 spec 的交付流程

1. 定位唯一 spec，读取 [项目规范](../AGENTS.md)、共享契约、直接依赖及完成证据。
2. 确认前置实现可用，列出本篇实施和验证清单；已授权范围内直接继续。
3. 根据交付物采用后端、前端、混合或实际引擎验收流程。
4. 更新本篇完成记录、阶段索引及受影响总索引，记录实际检查和未完成项。
5. 仅必需验收全部通过才标记完成；默认不自动进入下一篇，不自动提交或部署。

MVP-01 是第一步：验证当前分支引擎与候选 Pybatfish 的真实兼容性。它使用临时环境，不要求先创建 MVP-02 后端骨架。MVP-25 缺真实引擎或双用户浏览器证据时，保持待验证/未通过，不能进入 ADV-01。

## 连续执行 MVP 或显式新批次

项目级 [mvp-runner](../../.claude/skills/mvp-runner/SKILL.md) 复用 `spec-dev`，不改写每篇需求。启动方式：

```text
$mvp-runner
```

默认从首个未完成/待验证篇接续到 MVP-25。也可以限制范围或恢复：

```text
$mvp-runner MVP-03..MVP-10
$mvp-runner resume
```

CMDB/SIM 不会因默认 MVP 运行而自动开始。确认[共享设计](cmdb-simulation-design.md)和两期 spec 后，可显式使用：

```text
$mvp-runner CMDB-01..CMDB-11
$mvp-runner CMDB-01..SIM-17
```

单篇可用 `$spec-dev CMDB-01` 或 `$spec-dev SIM-01`。跨期范围在 CMDB-11 门槛未通过时停止，不跳入 SIM；新批次进度与 checkpoint 与旧 MVP 分开保存。

这些是给智能体的指令，不是终端可执行命令。启动连续流程即采用“实现 → 审查 → 当前及此前范围累计验收 → 回写 → commit → 下一篇”，不逐篇等待确认。单独执行 `$spec-dev <ID>` 仍默认停在本篇且不自动提交。

runner 运行时维护 MVP 的 `web/docs/plans/mvp-rollout.md` 或新批次的 `web/docs/plans/cmdb-simulation-rollout.md`，共用 `web/docs/validation-matrix.md`；恢复提示分别存于忽略提交的 `web/.runtime/mvp-runner/checkpoint.json` 和 `cmdb-simulation-checkpoint.json`。仅规划时不生成假进度。恢复时交叉核对 Git、实现、验收与 checkpoint，不仅凭同名 commit 或状态标签跳过工作。

每篇都使用 [真实服务与两套配置环境](test-lab.md)，无须真实路由器或现场结果对照。后端、PostgreSQL、SDK、已有前端及浏览器/部署检查按矩阵累计；`lab.py verify` 当前只覆盖后端。必需检查被跳过、环境缺失或运行服务仍是旧代码都不允许提交。API/worker 更新后应刷新实际服务；当前 lab 数据库重建会清空临时数据，需重新迁移和初始化。

用户及其他任务的未提交改动保持原样。批次准备所需基础设施只有在归属及提交授权明确时才做准备提交，不用 `git add .` 把整个工作区混入本篇。验证后实现发生变化要重新验收；提交失败或必要环境无法恢复时保留断点并报告阻碍。

截止篇验收并提交后停止；默认 MVP-25 必须包含真实服务、双用户页面闭环和两套配置证据。不会自动进入 ADV、推送、合并或发布到共享/生产环境。技能本身不提供后台定时唤醒；执行中断后从记录恢复。

**本次 CMDB/SIM 规划与技能扩展不启动连续批次。** 原 MVP 技能安装验证范围与场景见 [历史验证记录](evidence/mvp-runner-skill-validation.md)。

## 上游来源与更新

- 仓库：[mattpocock/skills](https://github.com/mattpocock/skills)。安装日期：2026-09-24。
- 固定 revision：`c55ee46073ed923f86ce59a5eb3b6d895095d1b7`。
- 安装路径：`skills/productivity/grill-me`、`skills/productivity/grilling`，保留上游正文与 `agents/openai.yaml`。
- [grill-me 固定版本](https://github.com/mattpocock/skills/blob/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/productivity/grill-me/SKILL.md)；[grilling 固定版本](https://github.com/mattpocock/skills/blob/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/productivity/grilling/SKILL.md)。

更新时在临时目录获取指定版本，比较两份 skill 及其依赖变化，再更新项目内实体和此版本记录；不直接覆盖本项目 `spec-dev`。首次安装使用官方 skill-installer 的 GitHub 安装脚本并显式指定项目目录，未安装上游仓库中的其他技能。

Codex 的项目技能目录及符号链接机制见 [官方技能说明](https://developers.openai.com/codex/skills/)，项目规范机制见 [AGENTS.md 说明](https://developers.openai.com/codex/guides/agents-md/)。
