import { useEffect, useState } from "react";
import { Select, Button, Space } from "antd";
import { useResourceContext } from "../../app/context";
import { useNetworks, useSnapshots } from "./queries";
export function ContextPicker() {
  const { network, snapshot, selectNetwork, selectSnapshot } =
    useResourceContext();
  const [networkSearch, setNetworkSearch] = useState("");
  const [snapshotSearch, setSnapshotSearch] = useState("");
  const networks = useNetworks();
  const snapshots = useSnapshots(network?.id ?? null);
  const ns = networks.data?.pages.flatMap((p) => p.items) ?? [];
  const ss = snapshots.data?.pages.flatMap((p) => p.items) ?? [];
  useEffect(() => {
    if (
      networkSearch &&
      !ns.some((n) =>
        `${n.display_name} · ${n.id.slice(0, 8)}`
          .toLowerCase()
          .includes(networkSearch.toLowerCase()),
      ) &&
      networks.hasNextPage &&
      !networks.isFetching &&
      !networks.isError
    )
      void networks.fetchNextPage();
  }, [networkSearch, ns, networks]);
  useEffect(() => {
    if (
      snapshotSearch &&
      !ss.some((s) =>
        `${s.display_name} · ${s.id.slice(0, 8)}`
          .toLowerCase()
          .includes(snapshotSearch.toLowerCase()),
      ) &&
      snapshots.hasNextPage &&
      !snapshots.isFetching &&
      !snapshots.isError
    )
      void snapshots.fetchNextPage();
  }, [snapshotSearch, ss, snapshots]);
  useEffect(() => setSnapshotSearch(""), [network?.id]);
  return (
    <div className="context-group">
      <label>
        当前网络
        <Select
          aria-label="当前网络"
          className="context-select"
          virtual={false}
          showSearch={{ optionFilterProp: "label", onSearch: setNetworkSearch }}
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
          virtual={false}
          showSearch={{
            optionFilterProp: "label",
            onSearch: setSnapshotSearch,
          }}
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
