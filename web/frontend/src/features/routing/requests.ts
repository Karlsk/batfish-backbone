import {
  defaultNodeProperties,
  defaultInterfaceProperties,
} from "../inventory/catalog";
import type { components } from "../../api/schema";
export type Operation = "nodes" | "interfaces" | "routes" | "lpm-routes";
export type RequestMap = {
  nodes: components["schemas"]["NodesRequest"];
  interfaces: components["schemas"]["InterfacesRequest"];
  routes: components["schemas"]["RoutesRequest"];
  "lpm-routes": components["schemas"]["LpmRequest"];
};
export type Selector =
  | components["schemas"]["LiteralSelector"]
  | components["schemas"]["ExpressionSelector"];
export type Draft = {
  mode: "literal" | "expression";
  names: string[];
  expression: string;
  interfaceMode: "literal" | "expression";
  interfaces: string[];
  interfaceExpression: string;
  vrfMode: "literal" | "expression";
  vrfs: string[];
  vrfExpression: string;
  destination: string;
  prefixMatch: NonNullable<
    components["schemas"]["RoutingOptions"]["prefix_match_type"]
  >;
  rib: "main" | "bgp";
  protocols: string[];
  properties: string[];
};
export const defaultDraft = (): Draft => ({
  mode: "literal",
  names: [],
  expression: "",
  interfaceMode: "literal",
  interfaces: [],
  interfaceExpression: "",
  vrfMode: "literal",
  vrfs: [],
  vrfExpression: "",
  destination: "",
  prefixMatch: "EXACT",
  rib: "main",
  protocols: [],
  properties: [],
});
export function selectorValue(
  mode: "literal" | "expression",
  values: string[],
  expression: string,
): Selector | null {
  if (mode === "expression")
    return expression.trim() ? { mode, expression: expression.trim() } : null;
  const names = [...new Set(values.map((n) => n.trim()).filter(Boolean))];
  return names.length ? { mode, values: names } : null;
}
export function ipv4(value: string) {
  return (
    /^(0|[1-9]\d{0,2})(\.(0|[1-9]\d{0,2})){3}$/.test(value) &&
    value.split(".").every((n) => Number(n) <= 255)
  );
}
export function prefix(value: string) {
  const [address, bits, extra] = value.split("/");
  if (
    extra !== undefined ||
    !ipv4(address) ||
    !/^(0|[1-9]\d?)$/.test(bits ?? "") ||
    Number(bits) > 32
  )
    return false;
  const number = address.split(".").reduce((a, b) => a * 256 + Number(b), 0);
  return number % 2 ** (32 - Number(bits)) === 0;
}
export function buildRequest<K extends Operation>(
  operation: K,
  draft: Draft,
): RequestMap[K] {
  const nodes = selectorValue(draft.mode, draft.names, draft.expression);
  const vrfs = selectorValue(draft.vrfMode, draft.vrfs, draft.vrfExpression);
  const destination = draft.destination.trim();
  let body: RequestMap[Operation];
  if (operation === "nodes")
    body = {
      options: {
        nodes,
        properties: (draft.properties.length
          ? draft.properties
          : [
              ...defaultNodeProperties,
            ]) as components["schemas"]["NodeOptions"]["properties"],
      },
    };
  else if (operation === "interfaces")
    body = {
      nodes,
      options: {
        interfaces: selectorValue(
          draft.interfaceMode,
          draft.interfaces,
          draft.interfaceExpression,
        ),
        properties: (draft.properties.length
          ? draft.properties
          : [
              ...defaultInterfaceProperties,
            ]) as components["schemas"]["InterfaceOptions"]["properties"],
      },
    };
  else if (operation === "lpm-routes") {
    if (!ipv4(destination))
      throw new Error("请输入有效的目标 IPv4 地址，不要填写 CIDR 前缀。");
    body = { ip: destination, nodes, options: { vrfs } };
  } else {
    if (destination && !prefix(destination))
      throw new Error("请输入规范 IPv4 CIDR，如 10.0.0.0/24，主机位必须为零。");
    body = {
      nodes,
      options: {
        vrfs,
        network: destination || null,
        rib: draft.rib,
        prefix_match_type: draft.prefixMatch,
        protocols: draft.protocols.length
          ? (draft.protocols as components["schemas"]["RoutingOptions"]["protocols"])
          : null,
      },
    };
  }
  return body as RequestMap[K];
}
