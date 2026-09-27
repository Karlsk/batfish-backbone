import type { components } from "../../../api/schema";

type Request = components["schemas"]["CreateConcernRequest"];
type Flow = components["schemas"]["ConcernFlow"];
export type ConcernDraft = {
  name: string;
  priority: Request["priority"];
  description?: string | null;
  flows: Array<{
    start_location: string;
    destination_ip: string;
    source_ip?: string | null;
    protocol?: Flow["protocol"];
    destination_port?: number | null;
  }>;
};

const ipv4 = (value: string) => {
  const parts = value.split(".");
  return (
    parts.length === 4 &&
    parts.every((part) => /^\d{1,3}$/.test(part) && Number(part) <= 255)
  );
};

export function prepareConcern(
  networkId: string,
  draft: ConcernDraft,
): Request {
  const name = draft.name?.trim();
  if (!name || name.length > 128) throw new Error("请输入不超过 128 字的名称");
  if (!draft.flows?.length || draft.flows.length > 10)
    throw new Error("请填写 1 至 10 条关键流量");
  const flows = draft.flows.map((value) => {
    const start_location = value.start_location?.trim();
    const destination_ip = value.destination_ip?.trim();
    const source_ip = value.source_ip?.trim() || undefined;
    const protocol = value.protocol || undefined;
    const destination_port = value.destination_port ?? undefined;
    if (!start_location || !destination_ip || !ipv4(destination_ip))
      throw new Error("请检查起点和目的 IPv4 地址");
    if (source_ip && !ipv4(source_ip)) throw new Error("请检查源 IPv4 地址");
    if (
      destination_port !== undefined &&
      ((protocol !== "tcp" && protocol !== "udp") ||
        !Number.isInteger(destination_port) ||
        destination_port < 0 ||
        destination_port > 65535)
    )
      throw new Error("目的端口仅能与 TCP 或 UDP 搭配，范围为 0–65535");
    return {
      start_location,
      destination_ip,
      ...(source_ip ? { source_ip } : {}),
      ...(protocol ? { protocol } : {}),
      ...(destination_port !== undefined ? { destination_port } : {}),
    };
  });
  return {
    network_id: networkId,
    name,
    priority: draft.priority,
    description: draft.description?.trim() || null,
    flows,
  };
}
