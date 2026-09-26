import { Button, Typography } from "antd";
import { Link } from "react-router-dom";
import { useResourceContext } from "../../app/context";
import { EmptyState } from "../../components/States";
import { TopologyForm } from "./TopologyForm";
export function TopologyPage() {
  const { network, snapshot } = useResourceContext();
  return (
    <>
      <Typography.Title level={2}>网络拓扑</Typography.Title>
      {network && snapshot ? (
        <TopologyForm
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
