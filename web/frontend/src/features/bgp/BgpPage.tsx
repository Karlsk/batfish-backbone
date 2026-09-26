import { Button, Typography } from "antd";
import { Link } from "react-router-dom";
import { useResourceContext } from "../../app/context";
import { EmptyState } from "../../components/States";
import { BgpForm } from "./BgpForm";
export function BgpPage() {
  const { network, snapshot } = useResourceContext();
  return (
    <>
      <Typography.Title level={2}>BGP 会话</Typography.Title>
      {network && snapshot ? (
        <BgpForm
          key={`${network.id}:${snapshot.id}`}
          networkId={network.id}
          snapshotId={snapshot.id}
        />
      ) : (
        <EmptyState
          title="请先选择网络与就绪快照"
          action={
            <Link to="/snapshots">
              <Button>选择快照</Button>
            </Link>
          }
        />
      )}
    </>
  );
}
