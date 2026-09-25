---
name: spec-dev
description: Use when implementing or resuming a Batfish Web MVP/ADV spec in this repository, including requests such as spec-dev MVP-01 or a path under web/docs/changeloge. Not for unrelated Java engine changes.
---

# Batfish 按 spec 开发

按一份已确认 spec 完成实现、相关验证和证据回写。项目约束统一保存在 `web/AGENTS.md`；本 skill 负责选篇、推进与验收，不重新生成另一套需求。

## 1. 定位输入和约束

- 接受 `MVP-01`、`mvp-01`、`ADV-01` 或本仓库具体 spec 路径；参数来自用户消息（支持该机制的客户端也可从 `$ARGUMENTS` 读取）。
- 从当前目录向上找到包含 `web/docs/changeloge/` 的仓库根目录；后续项目路径均相对此根目录。不要相对 skill 安装路径猜测项目目录。
- 编号忽略大小写，按完整 ID 加连字符匹配唯一文件：`mvp-01-*.md` 或 `adv-01-*.md`。先列实际文件再读取，不猜英文后缀；完整路径须解析到本仓库对应目录。
- 缺编号/路径、匹配为零或多个时，展示候选并询问；README、共享设计文档不是可执行 spec。
- 必读 `web/AGENTS.md`、目标 spec 全文、所在阶段 README、目标引用的共享契约相关章节，以及直接依赖的完成记录与交付物。更具体目录规范同样适用。

## 2. 开工判断

- 检查 git 现状、目标实现和前置交付物。依赖须有实现与通过证据；不能仅凭状态标签放行。缺失时报告具体前置 ID 和缺项，不顺带实现整条依赖链。
- 按实际交付内容判断后端、前端、混合或验收任务，不用 Hify 文件名规则。MVP-16 是前端骨架，MVP-22/23 含前后端，MVP-25 是真实闭环验收。
- 待开发项从首个未完成步骤开始；开发中项接续现状；待验证项优先补缺失验证，未通过项先复核失败证据、修复并复验；已完成项先说明现有证据，用户明确要求修复/复验时执行该增量，不重复造一遍。
- 已确认范围内列出简短实施与验证清单后继续，不设置固定“任务列表审批”停点。只将实质需求冲突、破坏公共契约或缺失的用户决策提问；继续不依赖答案的工作。
- 目标超过 2 人天时按项目规范拆分并更新依赖。保留已确认需求，不通过改写验收标准使结果变绿。

## 3. 执行与工具选择

- 按验收行为建立必要测试，再实现最小改动；测试关注权限、参数合并、状态、结果和上下文隔离。纯文档/视觉工作使用对应检查。
- 技术决策和边界遵循 `web/AGENTS.md` 及原 spec，尤其是 `api → service → controller`、跨模块 service、校验后的 options、Session 独占。
- Superpowers 已可用时，按实际工作使用 `writing-plans`、`test-driven-development`、`systematic-debugging`、`verification-before-completion`；读取适用技能后执行。不把每篇已定稿 spec 都重新送去完整需求访谈。
- 用户要求压测方案或确有未决设计时使用项目级 `grill-me`/`grilling`。先查事实，再询问用户决策；已有明确答复直接作为输入。用户指定单题节奏时遵循该偏好。
- `grill-me` 是调用 `grilling` 的上游入口。环境没有 Skill 调用工具时，依次读取 `.claude/skills/grill-me/SKILL.md` 和 `.claude/skills/grilling/SKILL.md` 并执行正文，不虚构工具调用。
- Superpowers 不可用时，说明未加载，继续按本 skill 的计划、测试、实现和验收步骤执行。这里不强制安装或初始化 Spec-Kit，不依赖 `speckit-*` 命令。

## 4. 选择验证方式

| 类型 | 验证依据 |
| --- | --- |
| MVP-01 | 在 `web/backend` 使用该 spec 的临时 uv/Python/SDK 命令；后端骨架尚不存在。连接隔离引擎并记录本分支 revision；不能以 mock 代替。 |
| 后端 | 检查实际 pyproject/锁文件，运行目标 pytest 和受影响检查；迁移/队列验证使用隔离 PostgreSQL。 |
| 前端 | 检查实际 package.json 与锁文件，运行目标 Vitest、类型检查和构建；按 spec 做页面/浏览器验证。 |
| 混合项 | 执行两侧相关检查，核对 OpenAPI、生成类型及前后端行为一致。 |
| 阶段验收 | 按 `web/docs/validation.md` 执行实际引擎及浏览器闭环；MVP-25、ADV-10、ADV-18 不以单元测试替代。 |

命令以目标 spec 和已存在项目脚本为准。不运行其他项目的 Go 门禁，不凭空假定脚本存在，不把跳过或未执行说成通过。缺少真实测试环境时完成已授权范围内可独立交付的代码/测试，依目标 spec 保留待验证/未通过状态，列出缺失条件；MVP-01 未取得引擎证据时明确记为未通过。用户仅要求检查时，保持只读，不实施产品或改写 spec 状态。

## 5. 回写与交付

将本篇状态更新为“开发中”“待验证”“未通过”或“已完成”，以实际情况为准；同步阶段索引和受影响总索引。仅全部必需验收通过才标“已完成”。原 spec 的完成记录至少包含：

- 日期、实际改动文件及对应需求；
- 实际验证命令、工作目录、结果，涉及 SDK 时的引擎/SDK/Python 版本；
- 未执行/失败的检查、环境缺口和已知限制；
- 是否满足下一项依赖或阶段门槛。

最终给出本篇 ID/状态、主要行为变化、验证证据和剩余阻碍。默认停在本篇交付，不自动进入下一篇，不提交/推送/部署。

当用户已启动项目级 `mvp-runner` 连续执行时，本 skill 仍只完成当前篇；累计回归、提交与选择下一篇由 runner 按用户授权处理。不要为此重复询问已授权的提交，也不要独自越过 runner 的累计验收门槛。仅创建/检查 runner skill 不算启动批次。
