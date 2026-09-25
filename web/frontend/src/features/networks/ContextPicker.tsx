import { Select, Button, Space } from "antd";
import { useResourceContext } from "../../app/context";
import { useNetworks, useSnapshots } from "./queries";
export function ContextPicker() {
  const { network, snapshot, selectNetwork, selectSnapshot } =
    useResourceContext();
  const networks = useNetworks();
  const snapshots = useSnapshots(network?.id ?? null);
  const ns = networks.data?.pages.flatMap((p) => p.items) ?? [];
  const ss = snapshots.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <div className="context-group">
      <label>
        当前网络
        <Select
          aria-label="当前网络"
          className="context-select"
          showSearch={{ optionFilterProp: "label" }}
          value={network?.id}
          loading={networks.isFetching}
          placeholder="选择网络"
          options={[
            ...ns.map((n) => ({
              value: n.id,
              label: `${n.display_name} · ${n.id.slice(0, 8)}`,
              disabled: n.sync_state !== "ready",
            })),
            ...(network && !ns.some((n) => n.id === network.id)
              ? [{ value: network.id, label: network.name }]
              : []),
          ]}
          onChange={(id) => {
            const n = ns.find((n) => n.id === id);
            if (n) void selectNetwork({ id: n.id, name: n.display_name });
          }}
          popupRender={(menu) => (
            <>
              {menu}
              {networks.hasNextPage && (
                <Button block onClick={() => void networks.fetchNextPage()}>
                  加载更多网络
                </Button>
              )}
            </>
          )}
          notFoundContent={networks.isError ? "网络加载失败" : "暂无网络"}
        />
      </label>
      <span className="context-divider">/</span>
      <label>
        当前快照
        <Select
          aria-label="当前快照"
          className="context-select"
          showSearch={{ optionFilterProp: "label" }}
          disabled={!network}
          value={snapshot?.id}
          loading={snapshots.isFetching}
          placeholder="选择快照"
          options={[
            ...ss.map((s) => ({
              value: s.id,
              label: `${s.display_name} · ${s.id.slice(0, 8)}`,
            })),
            ...(snapshot && !ss.some((s) => s.id === snapshot.id)
              ? [{ value: snapshot.id, label: snapshot.name }]
              : []),
          ]}
          onChange={(id) => {
            const s = ss.find((s) => s.id === id);
            if (s)
              void selectSnapshot({
                id: s.id,
                name: s.display_name,
                networkId: s.network_id,
              });
          }}
          popupRender={(menu) => (
            <>
              {menu}
              {snapshots.hasNextPage && (
                <Button block onClick={() => void snapshots.fetchNextPage()}>
                  加载更多快照
                </Button>
              )}
            </>
          )}
          notFoundContent={snapshots.isError ? "快照加载失败" : "暂无快照"}
        />
      </label>
    </div>
  );
}
