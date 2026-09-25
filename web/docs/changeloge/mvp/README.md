# 第一阶段：基础排障闭环

状态：MVP-01～03 已完成，其余22份待开发。总计25份，预计40.0人天，单份≤2人天。

阶段目标：内置账号、共享网络/快照、上传与解析诊断、设备/接口、路由/LPM、单向IPv4 traceroute、任务、导出及对应前端。不包含拓扑/BGP/ACL专页和变更验证。

| Spec | 依赖 | 工作量（人天） | 状态 |
| --- | --- | ---: | --- |
| [MVP-01 SDK 兼容性与能力基线](mvp-01-sdk-compatibility.md) | 无 | 1.0 | 已完成 |
| [MVP-02 后端骨架与分层约束](mvp-02-backend-foundation.md) | MVP-01 | 1.0 | 已完成 |
| [MVP-03 业务持久化与迁移基础](mvp-03-persistence.md) | MVP-02 | 1.5 | 已完成 |
| [MVP-04 登录、改密与可撤销会话](mvp-04-authentication.md) | MVP-03 | 2.0 | 待开发 |
| [MVP-05 账号管理与基础审计](mvp-05-user-administration.md) | MVP-04 | 1.5 | 待开发 |
| [MVP-06 网络创建与共享查询](mvp-06-network-management.md) | MVP-05 | 1.0 | 待开发 |
| [MVP-07 配置上传与输入校验](mvp-07-configuration-upload.md) | MVP-06 | 2.0 | 待开发 |
| [MVP-08 任务记录、幂等与排队取消](mvp-08-job-records.md) | MVP-07 | 1.5 | 待开发 |
| [MVP-09 独立执行进程与中断恢复](mvp-09-worker-recovery.md) | MVP-08 | 2.0 | 待开发 |
| [MVP-10 快照初始化与不可变生命周期](mvp-10-snapshot-initialization.md) | MVP-09 | 2.0 | 待开发 |
| [MVP-11 解析质量与原始文件查看](mvp-11-initialization-diagnostics.md) | MVP-10 | 1.5 | 待开发 |
| [MVP-12 分析目录与结果标准化](mvp-12-analysis-results.md) | MVP-11 | 2.0 | 待开发 |
| [MVP-13 设备与接口分析接口](mvp-13-inventory.md) | MVP-12 | 1.5 | 待开发 |
| [MVP-14 路由与最长前缀匹配接口](mvp-14-routing.md) | MVP-13 | 1.5 | 待开发 |
| [MVP-15 IPv4 单向虚拟 traceroute 接口](mvp-15-traceroute.md) | MVP-14 | 2.0 | 待开发 |
| [MVP-16 前端骨架与渐进展示组件](mvp-16-frontend-foundation.md) | MVP-12 | 1.5 | 待开发 |
| [MVP-17 登录与用户管理界面](mvp-17-frontend-auth-users.md) | MVP-05、MVP-16 | 1.5 | 待开发 |
| [MVP-18 网络、快照与上传向导界面](mvp-18-frontend-networks-snapshots.md) | MVP-10、MVP-17 | 2.0 | 待开发 |
| [MVP-19 任务记录与解析诊断界面](mvp-19-frontend-jobs-diagnostics.md) | MVP-11、MVP-18 | 1.5 | 待开发 |
| [MVP-20 设备、接口与路由界面](mvp-20-frontend-inventory-routing.md) | MVP-13、MVP-14、MVP-19 | 2.0 | 待开发 |
| [MVP-21 连通性表单与逐跳路径界面](mvp-21-frontend-traceroute.md) | MVP-15、MVP-20 | 2.0 | 待开发 |
| [MVP-22 结果导出与下载入口](mvp-22-result-export.md) | MVP-21 | 1.0 | 待开发 |
| [MVP-23 管理员资源删除与任务互斥](mvp-23-resource-deletion.md) | MVP-22 | 1.5 | 待开发 |
| [MVP-24 单机团队部署与运行手册](mvp-24-deployment.md) | MVP-23 | 1.5 | 待开发 |
| [MVP-25 首版双用户验收与规模校准](mvp-25-mvp-acceptance.md) | MVP-24 | 1.5 | 待开发 |

MVP-01～15建立后端闭环；MVP-16前端公共骨架只依赖已稳定的结果契约，可在接口稳定后开始，但这里按默认后端先行顺序排列。MVP-22/23补齐导出和清理，MVP-24部署，MVP-25完成双用户和真实引擎验收。通过后进入 [第二阶段](../advance/README.md)。

规则与总工时见 [规格总索引](../README.md)。
