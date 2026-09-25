import type { components } from "../../api/schema";
export type Job = components["schemas"]["JobDTO"];
type Identity = Pick<
  components["schemas"]["SessionInfo"],
  "user_id" | "role"
> | null;
export const jobLabels: Record<Job["status"], string> = {
  queued: "排队中",
  running: "执行中",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
  interrupted: "执行中断",
};
export const kindLabels: Record<Job["kind"], string> = {
  upload: "上传",
  initialization: "初始化",
  analysis: "分析",
  deletion: "删除",
};
export const phaseLabels: Record<string, string> = {
  queued: "等待调度",
  starting: "准备执行",
  checking_cache: "检查已有结果",
  querying: "查询模型",
  dataplane_or_query: "构建数据平面或查询",
  succeeded: "处理完成",
  failed: "处理失败",
  cancelled: "已取消排队",
  interrupted: "执行已中断",
};
export function pollInterval(job?: Job) {
  if (!job || !["queued", "running"].includes(job.status))
    return job ? false : 2000;
  return Date.now() - Date.parse(job.created_at) < 30000 ? 2000 : 5000;
}
export function ownsJob(job: Job, identity: Identity) {
  return (
    !!identity &&
    (identity.role === "admin" || job.created_by === identity.user_id)
  );
}
export function canCancel(job: Job, identity: Identity) {
  return (
    job.cancel_allowed && job.status === "queued" && ownsJob(job, identity)
  );
}
export function canRetry(job: Job, identity: Identity) {
  return (
    ["failed", "cancelled", "interrupted"].includes(job.status) &&
    ["initialization", "analysis"].includes(job.kind) &&
    ownsJob(job, identity)
  );
}

export function durationLabel(job: Job) {
  if (!job.started_at) return "尚未开始";
  const end = job.finished_at ? Date.parse(job.finished_at) : Date.now();
  const seconds = Math.max(
    0,
    Math.floor((end - Date.parse(job.started_at)) / 1000),
  );
  return seconds >= 60
    ? `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`
    : `${seconds} 秒`;
}
