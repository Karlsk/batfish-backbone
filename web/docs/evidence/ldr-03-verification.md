# LDR-03 业务关注项页面验收

日期：2026-09-28；基线提交：`b2e78f9c2f`（LDR-02）。状态：LDR-03 已实现，依赖与累计前端门槛通过。

领导端新增 `/leader/concerns`。选定网络后显示关注项名称、重要程度、关键流量数和映射版本；同名网络在选择器中附加短 ID。管理员可用名称、重要程度、起点与目的 IPv4 建立映射，源地址、协议与端口折叠且编辑后回填；提交前显示所有生效流量。成员只读。详情按需读取旧版本；归档后默认列表消失，提示旧汇报仍保留原版本事实。查询键包含用户与网络，切换网络会销毁旧网络的表单及详情状态。并发旧版本更新显示冲突且保留填写值。

| 检查 | 结果 |
| --- | --- |
| 表单行为 | 先运行 `pnpm exec vitest run src/features/leader/concerns/draft.test.ts` 得到缺实现的预期失败；实现后通过 2 项，覆盖多流量高级条件保留及非法范围拒绝。 |
| 前端累计单测 | 在 `web/frontend` 运行 `pnpm test`：29 文件、96 passed。 |
| API 类型与构建 | `pnpm check:api`、`pnpm typecheck`、`pnpm build` 通过；`pnpm format:check` 与 `git diff --check` 通过。 |
| 真实双用户浏览器 | 隔离 PostgreSQL 升级至 `0011`，对固定 Batfish 测试环境另启当前源码 API（18001），Vite 代理指向该 API；Playwright 运行 `tests/leader-concerns.spec.ts` 2 passed。管理员创建/编辑/旧版/归档与网络切换、成员只读和并发 409 保留草稿均通过。 |
| 既有入口回归 | 同一隔离环境运行 `tests/leader-concerns.spec.ts tests/leader-entry.spec.ts`：5 passed；技术端默认入口、模式/主题切换、网络和快照上下文保持通过。 |
| 页面检查 | Chromium 亮色、深色页面截图已生成并目视检查；重要程度标签及主要按钮对比度修正。 |

隔离环境运行 ID `8a53df3cb24f`，Batfish revision `7d0deeeac4a09973b3876327f6aef721ee12f955`、Pybatfish `2026.9.17.3748`、Python `3.12.12`。本篇不执行分析或判断业务影响。此前截图中的“服务尚未就绪”因无 URL/网络/快照不能定位为同一请求；未将其标为已修复。LDR-04 可基于已验收的关注项和现有网络、快照 service 继续。
