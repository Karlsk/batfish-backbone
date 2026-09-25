import { Alert, Button, Empty, Spin } from "antd";
import { ApiError } from "../api/client";
export function ErrorState({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <Alert
      type="error"
      showIcon
      title={
        error instanceof ApiError ? error.message : "加载失败，请稍后重试。"
      }
      description={
        error instanceof ApiError && error.requestId
          ? `请求编号：${error.requestId}`
          : undefined
      }
      action={retry ? <Button onClick={retry}>重试</Button> : undefined}
    />
  );
}
export function EmptyState({
  title = "暂无数据",
  description,
  action,
}: {
  title?: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <Empty
      description={
        <>
          <strong>{title}</strong>
          {description && <p>{description}</p>}
        </>
      }
    >
      {action}
    </Empty>
  );
}
export function LoadingState() {
  return (
    <div className="loading-state" role="status">
      <Spin /> 正在加载…
    </div>
  );
}
