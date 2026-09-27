import { Badge } from "antd";
import { useQuery } from "@tanstack/react-query";
import { resourceKey } from "./context";
import { api, unwrap } from "../api/client";

export function ServiceStatus() {
  const health = useQuery({
    queryKey: resourceKey(
      null,
      { networkId: null, snapshotId: null },
      "health",
    ),
    queryFn: () => unwrap(api.GET("/api/v1/health/ready")),
    refetchInterval: 30000,
  });
  return (
    <Badge
      status={
        health.isSuccess
          ? "success"
          : health.isPending
            ? "processing"
            : "warning"
      }
      text={
        health.isSuccess
          ? "服务就绪"
          : health.isPending
            ? "正在连接"
            : "服务未就绪"
      }
    />
  );
}
