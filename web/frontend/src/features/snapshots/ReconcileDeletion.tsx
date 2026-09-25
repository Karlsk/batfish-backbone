import { useState, useRef, useEffect } from "react";
import { Alert, Button, Card, Form, Input } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { api, unwrap, ApiError } from "../../api/client";
import type { components } from "../../api/schema";
import { useSession } from "../../app/session";
import { ErrorState } from "../../components/States";
export function ReconcileDeletion({
  job,
}: {
  job: components["schemas"]["JobDTO"];
}) {
  const session = useSession(),
    client = useQueryClient();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [state, setState] = useState<string>();
  const flight = useRef(false),
    alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  if (
    job.kind !== "deletion" ||
    !["failed", "interrupted"].includes(job.status)
  )
    return null;
  return (
    <Card title="删除状态待对账">
      <Alert
        type="warning"
        showIcon
        title="删除未能确认完成，资源可能仍处于删除中。"
        description="不能直接重试删除。管理员核对远端资源：仍存在则恢复可用状态，不存在则补记已删除；无法确认时保持阻塞。若引擎状态未知，需先按运行手册停止旧执行进程、确认引擎空闲并完成引擎对账。"
      />
      {session?.role === "admin" && (
        <Form
          layout="vertical"
          onFinish={async ({ note }) => {
            if (flight.current) return;
            flight.current = true;
            setBusy(true);
            setError(undefined);
            try {
              const result = await unwrap(
                api.POST("/api/v1/admin/deletions/{job_id}/reconcile", {
                  params: { path: { job_id: job.id } },
                  body: { note },
                }),
              );
              if (alive.current) setState(result.state);
              void client.invalidateQueries({ queryKey: ["resource"] });
            } catch (failure) {
              if (alive.current) setError(failure);
            } finally {
              flight.current = false;
              if (alive.current) setBusy(false);
            }
          }}
        >
          <Form.Item
            label="对账说明"
            name="note"
            rules={[
              {
                required: true,
                min: 10,
                max: 1000,
                message: "请填写10～1000字的检查说明",
              },
            ]}
          >
            <Input.TextArea disabled={busy || !!state} />
          </Form.Item>
          <Button
            htmlType="submit"
            loading={busy}
            disabled={!!state}
            aria-label="检查远端并对账"
          >
            检查远端并对账
          </Button>
        </Form>
      )}
      {error instanceof ApiError && error.code === "CONFLICT" ? (
        <Alert
          type="warning"
          title="仍有活动任务、引擎未对账或该删除任务已被后续操作替代，请检查后再试。"
        />
      ) : (
        error !== undefined && <ErrorState error={error} />
      )}
      {state && (
        <Alert
          type="success"
          title={
            state === "deleted"
              ? "已确认远端删除，保留历史结果。"
              : "远端资源仍存在，已恢复资源状态。"
          }
          description="原删除任务保留失败/中断记录；如仍需删除，请从资源列表重新确认。"
        />
      )}
    </Card>
  );
}
