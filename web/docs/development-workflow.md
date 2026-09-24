# 按 spec 推进 Batfish Web

采用项目专用 `spec-dev` 作为开发入口，Superpowers 提供按需计划、测试、调试和验证方法，`grill-me` 用于未决方案的交互澄清。已有 25 份 MVP 和 18 份 ADV spec 是需求与验收依据；本流程不初始化 Spec-Kit，不复制一套平行需求文件。

## 项目级安装布局

```text
.claude/skills/
├── spec-dev/             # 本项目专用
├── grill-me/             # 上游访谈入口
└── grilling/             # 上游访谈实现，grill-me 的依赖
.agents/skills/
├── spec-dev -> ../../.claude/skills/spec-dev
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

这些是发给智能体的指令，不是 shell 命令。MVP-16 示例仅展示路径格式；依赖未满足时会指出缺失项，不会越过前序验收。每篇完成后再调用下一篇；所有篇目和依赖见 [MVP 索引](changeloge/mvp/README.md) 与 [ADV 索引](changeloge/advance/README.md)。

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

## 上游来源与更新

- 仓库：[mattpocock/skills](https://github.com/mattpocock/skills)。安装日期：2026-09-24。
- 固定 revision：`c55ee46073ed923f86ce59a5eb3b6d895095d1b7`。
- 安装路径：`skills/productivity/grill-me`、`skills/productivity/grilling`，保留上游正文与 `agents/openai.yaml`。
- [grill-me 固定版本](https://github.com/mattpocock/skills/blob/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/productivity/grill-me/SKILL.md)；[grilling 固定版本](https://github.com/mattpocock/skills/blob/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/productivity/grilling/SKILL.md)。

更新时在临时目录获取指定版本，比较两份 skill 及其依赖变化，再更新项目内实体和此版本记录；不直接覆盖本项目 `spec-dev`。首次安装使用官方 skill-installer 的 GitHub 安装脚本并显式指定项目目录，未安装上游仓库中的其他技能。

Codex 的项目技能目录及符号链接机制见 [官方技能说明](https://developers.openai.com/codex/skills/)，项目规范机制见 [AGENTS.md 说明](https://developers.openai.com/codex/guides/agents-md/)。
