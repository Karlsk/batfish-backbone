import { useEffect, useRef, useState } from "react";
import { Alert, Button, Modal } from "antd";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, unwrap } from "../../api/client";
import { useResourceContext } from "../../app/context";
import { useSession } from "../../app/session";
import { ErrorState } from "../../components/States";
export function DeleteResource({
  networkId,
  snapshotId,
  name,
  state,
  jobId,
}: {
  networkId: string;
  snapshotId?: string;
  name: string;
  state: string;
  jobId?: string | null;
}) {
  const context = useResourceContext();
  const latestContext = useRef(context);
  latestContext.current = context;
  const session = useSession(),
    client = useQueryClient(),
    navigate = useNavigate();
  const [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const inFlight = useRef(false),
    alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  if (session?.role !== "admin") return null;
  if (state === "deleting")
    return jobId ? (
      <Link to={`/jobs/${jobId}`}>删除任务</Link>
    ) : (
      <span>删除中</span>
    );
  if (state === "deleted") return null;
  const kind = snapshotId ? "快照" : "网络";
  async function remove() {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(undefined);
    try {
      const job = snapshotId
        ? await unwrap(
            api.DELETE(
              "/api/v1/networks/{network_id}/snapshots/{snapshot_id}",
              {
                params: {
                  path: { network_id: networkId, snapshot_id: snapshotId },
                },
              },
            ),
          )
        : await unwrap(
            api.DELETE("/api/v1/networks/{network_id}", {
              params: { path: { network_id: networkId } },
            }),
          );
      void client.invalidateQueries({ queryKey: ["resource"] });
      if (alive.current) {
        const current = latestContext.current;
        if (!snapshotId && current.network?.id === networkId)
          await current.selectNetwork(null);
        else if (snapshotId && current.snapshot?.id === snapshotId)
          await current.selectSnapshot(null);
        if (!alive.current) return;
        setOpen(false);
        navigate(`/jobs/${job.id}`);
      }
    } catch (failure) {
      if (alive.current) setError(failure);
      void client.invalidateQueries({ queryKey: ["resource"] });
    } finally {
      inFlight.current = false;
      if (alive.current) setBusy(false);
    }
  }
  return (
    <>
      <Button
        danger
        type="link"
        disabled={!snapshotId && state !== "ready"}
        onClick={() => {
          setError(undefined);
          setOpen(true);
        }}
      >
        删除{kind}
      </Button>
      <Modal
        title={`确认删除${kind}`}
        open={open}
        onCancel={() => {
          if (!busy) setOpen(false);
        }}
        onOk={() => void remove()}
        okText="确认删除"
        cancelText="保留资源"
        confirmLoading={busy}
        okButtonProps={{ danger: true, "aria-label": "确认删除" }}
        cancelButtonProps={{ disabled: busy }}
        closable={!busy}
        mask={{ closable: !busy }}
      >
        <p>
          <strong>{name}</strong>
        </p>
        <p className="record-id">资源编号：{snapshotId ?? networkId}</p>
        <p>
          删除后不能再基于此资源执行分析；已保存结果和来源信息继续保留。删除任务排队后不可取消。
        </p>
        {!snapshotId && <p>网络必须先逐个删除全部快照，本操作不会批量删除。</p>}
        {error instanceof ApiError && error.code === "CONFLICT" ? (
          <Alert
            type="warning"
            showIcon
            title="存在活动任务、未删除快照或待对账状态，请查看资源与任务列表。"
          />
        ) : (
          error !== undefined && <ErrorState error={error} />
        )}
        {error !== undefined && (
          <p>列表已刷新；请求结果不确定时，请检查是否已经生成删除任务。</p>
        )}
      </Modal>
    </>
  );
}
