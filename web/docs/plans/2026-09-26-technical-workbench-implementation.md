# 技术工作台双主题升级实施计划

> **For agentic workers:** 使用 superpowers:executing-plans 在当前会话逐项实施，最终进行一次独立只读审查。

**Goal:** 完成现有技术工作台全部页面的深浅双主题升级，保留真实业务流程。

**Architecture:** 主题偏好独立于身份和资源状态；Ant Design 配置与 CSS 语义变量统一管理。结果以已保存 DTO 为唯一来源，不新增后端能力或示例统计。

**Tech Stack:** 现有 React / TypeScript / Ant Design / Vite / Vitest / Playwright，不新增依赖。

**Spec:** [已确认设计](2026-09-26-technical-workbench-design.md)。用户最新指令为“只完成技术工作台双主题升级，其他暂时先不做”，本计划记录后在当前工作区直接完成该范围，不启动 ADV、领导端或自动提交。

## 全局约束

- 保留现有 API、SDK、数据库、权限、会话、查询缓存和任务执行语义。
- light/dark/system 三种偏好；默认跟随系统，存储不可用不能阻塞，切换不重新挂载业务页面。
- 所有已有页面及浮层适配；普通正文14px，表格/配置至少12px，视觉对比度按设计实测。
- 不更改未归属本任务的 `.pnpm-store/` 或其他用户文件；沿用已有 codex 开发分支，本次不提交。

## Review Focus

1. 存储抛错/损坏值/浏览器系统偏好变更：仍能登录且主题可切换；任务1覆盖。
2. 首屏与应用主题不同、暗色浮层残留白底：启动脚本一致性及生产页面/浮层检查；任务1/3覆盖。
3. 主题切换重置表单、上下文或 QueryClient：有状态组件与真实表单检查；任务1/3覆盖。
4. 摘要把当前分页数量或示例耗时冒充全量：仅取保存DTO；任务2检查。
5. 长名称、小屏、源行高亮与危险操作：1280/1440/1920和窄视口，真实诊断/删除回归；任务3覆盖。

### Task 1: 主题偏好与全站基础样式（预计1.5人天）

**Files:** 新增 `frontend/src/app/theme.tsx`、主题样式、`frontend/public/theme-init.js`、`frontend/src/app/theme.test.tsx`；修改 `App.tsx`、`index.html`、`Auth.tsx`、`style.css`。

**Interfaces:** `ThemeProvider({children})` 提供Ant主题而不持有业务缓存；`ThemeControl()` 提供三态按钮。根节点 `data-theme=light|dark`，浏览器键 `batfish-theme-preference` 保存 `light|dark|system`。

- [x] 先测试无主题按钮/系统响应的失败基线；覆盖显式选择、系统变化、刷新初始化、存储损坏/抛错、组件状态和缓存实例保留。
- [x] 实现独立主题provider及首屏脚本，登录/强制改密/壳层提供一致入口。
- [x] 全部硬编码色转语义变量，覆盖导航、标题、卡片、表格、配置、focus和reduced-motion。
- [x] `pnpm test`、`pnpm build` 通过；不对低风险纯CSS写镜像断言。

### Task 2: 查询、结果和现有页面视觉适配（预计1.5人天）

**Files:** `features/inventory/Analysis.tsx`、`features/results/Results.tsx`、`components/ResultSummary.tsx`、相关共用样式；检查所有features目录。

**Interfaces:** 使用任务1主题变量；结果数据继续使用 `ResultEnvelope`、既有 rows/flows接口与固定结果ID。

- [x] 整理页面标题、查询导航及表单层次，保留现有操作与标签。
- [x] 结果布局采用摘要/证据/来源面板；只展示DTO支持的行数、创建时间、固定来源和参数，不虚构设备数、耗时。
- [x] 登录、用户管理、网络快照、上传、任务、诊断、trace、导出和删除对账全部跟随主题。
- [x] `pnpm test`、`pnpm check:api`、`pnpm build`、`pnpm format:check` 通过。

### Task 3: 真实服务回归与交付（预计1.5人天）

**Files:** 新增 `frontend/tests/theme.spec.ts`，调整现有Playwright配置为可选择回归主题；更新 `docs/frontend.md`、设计状态、独立验收记录。

**Interfaces:** 使用现有lab、两套fixture、原浏览器测试及部署脚本；只管理已核对归属的本机服务。

- [x] 真实页面验证持久化/系统切换/表单保留、浮层和字体背景；在两种主题运行既有10项浏览器回归。
- [x] 在生产构建运行双用户闭环；检查深浅两套账号、快照、结果来源不串用。记录截图并实际查看。
- [x] 对已存在的真实服务执行smoke，源代码未变的后端复用环境，不修改Java或扩大到ADV验收。
- [x] 新增主题测试及全部前端检查通过；最终一次只读审查，修复实际缺陷并补受影响验证。
- [x] 回写版本、运行命令、计数、源码身份和限制；产品代码完成前不标记已交付。

## 执行记录

- 计划已按设计逐项自检：范围、数据来源、主题偏好与验证均有对应任务。
- 当前直接完成已授权范围，不再重复征询视觉或执行方式；采用主流程串行实现、最终一次只读审查。
- 无 Git 提交步骤：之前 MVP runner 的逐篇提交授权已随批次结束，本任务仅保留可审阅改动。

- 2026-09-26：三个任务已完成，测试与独立审查详见[验收记录](../evidence/technical-workbench-theme-2026-09-26.md)。正文与控件配色目标通过；浅色侧栏焦点环原2.993:1小项已在后续MVP全量复验时采用导航强调色修复。
