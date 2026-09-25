export function cellText(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return value.map(cellText).join("，");
  if (typeof value !== "object") return String(value);
  const v = value as Record<string, unknown>;
  if (v.type === "ip") return String(v.ip ?? "未提供地址");
  if (v.type === "interface")
    return `${v.interface ?? "未提供接口"}${v.ip ? ` → ${v.ip}` : ""}`;
  if (v.type === "discard") return "丢弃（discard）";
  if (v.type === "vrf") return `转入 VRF ${v.vrf ?? "未知"}`;
  if (typeof v.hostname === "string")
    return `${v.hostname}${v.interface ? `[${v.interface}]` : ""}`;
  if (typeof v.name === "string") return v.name;
  return JSON.stringify(value);
}
export const columnLabels: Record<string, string> = {
  Node: "设备",
  Hostname: "主机名",
  Configuration_Format: "配置格式",
  Interfaces: "接口",
  Interface: "接口",
  Description: "描述",
  Active: "启用",
  Primary_Address: "主地址",
  VRF: "VRF",
  Network: "路由前缀",
  Next_Hop: "下一跳",
  Next_Hop_IP: "下一跳 IP",
  Next_Hop_Interface: "下一跳接口",
  Protocol: "协议",
  Metric: "开销",
  Admin_Distance: "管理距离",
  Ip: "目标地址",
  Num_Routes: "匹配路由数",
};
export function primaryColumns(keys: string[]) {
  const priority = [
    "Node",
    "Interface",
    "VRF",
    "Network",
    "Next_Hop",
    "Protocol",
    "Ip",
    "Num_Routes",
    "Hostname",
    "Configuration_Format",
    "Interfaces",
    "Description",
    "Active",
    "Primary_Address",
  ];
  return [
    ...new Set([...priority.filter((k) => keys.includes(k)), ...keys]),
  ].slice(0, 6);
}
