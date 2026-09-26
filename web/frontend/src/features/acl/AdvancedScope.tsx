import { Alert, Form, Select } from "antd";
import { useQuery } from "@tanstack/react-query";
import type { components } from "../../api/schema";
import { api, unwrap } from "../../api/client";
import { useSession } from "../../app/session";
import { ErrorState } from "../../components/States";
import { useCandidates } from "../inventory/useCandidates";

type Capability = components["schemas"]["Capability"];

export function useAclCapability(id: string) {
  const session = useSession();
  const query = useQuery({
    queryKey: ["capabilities", session?.user_id ?? null],
    queryFn: ({ signal }) =>
      unwrap(api.GET("/api/v1/capabilities", { signal })),
  });
  return {
    query,
    capability: query.data?.find((item): item is Capability => item.id === id),
  };
}

export function AdvancedScope({
  networkId,
  snapshotId,
  nodes,
  filters,
  onNodes,
  onFilters,
}: {
  networkId: string;
  snapshotId: string;
  nodes: string[];
  filters: string[];
  onNodes: (value: string[]) => void;
  onFilters: (value: string[]) => void;
}) {
  const candidates = useCandidates(networkId, snapshotId);
  return (
    <>
      <Alert
        type="info"
        title="只查询明确选定的设备与 ACL，各最多10项；输入名称后按回车确认。"
      />
      {candidates.controls}
      <Form.Item label="设备范围">
        <Select
          aria-label="设备范围"
          mode="tags"
          virtual={false}
          tokenSeparators={[","]}
          value={nodes}
          options={candidates.nodes.map((value) => ({ value, label: value }))}
          onChange={onNodes}
          placeholder="选择候选设备或输入准确名称"
        />
      </Form.Item>
      <Form.Item label="ACL 范围">
        <Select
          aria-label="ACL 范围"
          mode="tags"
          virtual={false}
          tokenSeparators={[","]}
          value={filters}
          onChange={onFilters}
          placeholder="输入准确 ACL 名称"
        />
      </Form.Item>
    </>
  );
}

export function CapabilityState({
  query,
  capability,
}: {
  query: ReturnType<typeof useAclCapability>["query"];
  capability: Capability | undefined;
}) {
  if (query.isError)
    return (
      <ErrorState error={query.error} retry={() => void query.refetch()} />
    );
  if (query.isSuccess && (!capability || !capability.enabled))
    return (
      <Alert
        type="warning"
        title={capability?.disabled_reason || "当前环境未开放此 ACL 能力。"}
      />
    );
  return null;
}
