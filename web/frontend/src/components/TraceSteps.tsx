import { Button, Collapse, Space, Tag, Timeline } from "antd";
import { useState } from "react";
import { DetailsDrawer } from "./DetailsDrawer";
import { cellText } from "../features/results/cells";
export const record = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
export const list = (value: unknown): unknown[] =>
  Array.isArray(value) ? value : [];
const labels: Record<string, string> = {
  ACCEPTED: "模型接收",
  DELIVERED_TO_SUBNET: "送达子网",
  EXITS_NETWORK: "离开模型网络",
  NO_ROUTE: "没有路由",
  NULL_ROUTED: "丢弃路由",
  DENIED_IN: "入方向 ACL 拒绝",
  DENIED_OUT: "出方向 ACL 拒绝",
  LOOP: "检测到环路",
  NEIGHBOR_UNREACHABLE: "下一跳邻居不可达",
  INSUFFICIENT_INFO: "信息不足",
  ORIGINATED: "生成报文",
  FORWARDED: "路由转发",
  TRANSMITTED: "从接口发出",
  RECEIVED: "从接口接收",
  PERMITTED: "过滤规则允许",
  DENIED: "过滤规则拒绝",
  TRANSFORMED: "报文变换",
};
export function actionLabel(value: unknown) {
  const name = typeof value === "string" ? value : "UNKNOWN";
  return labels[name]
    ? `${labels[name]}（${name}）`
    : `未知或扩展动作（${name}）`;
}
export function TraceSteps({
  trace,
  identity,
  queryKey,
}: {
  trace: Record<string, unknown>;
  identity: string;
  queryKey: readonly unknown[];
}) {
  const [detail, setDetail] = useState<unknown>();
  const hops = list(trace.hops);
  return (
    <>
      <Timeline
        items={hops.map((h, index) => {
          const hop = record(h);
          return {
            title: `${index + 1}. ${cellText(hop.node)}`,
            content: (
              <Collapse
                items={list(hop.steps).map((s, i) => {
                  const step = record(s),
                    d = record(step.detail);
                  return {
                    key: String(i),
                    label: actionLabel(step.action),
                    children: (
                      <>
                        <Space orientation="vertical">
                          {d.inputInterface !== undefined && (
                            <span>入接口：{cellText(d.inputInterface)}</span>
                          )}
                          {d.outputInterface !== undefined && (
                            <span>出接口：{cellText(d.outputInterface)}</span>
                          )}
                          {d.vrf !== undefined && (
                            <span>VRF：{cellText(d.vrf)}</span>
                          )}
                          {d.filter !== undefined && (
                            <span>过滤器：{cellText(d.filter)}</span>
                          )}
                          {d.forwardingDetail !== undefined && (
                            <span>
                              转发信息：{cellText(d.forwardingDetail)}
                            </span>
                          )}
                          <Button type="link" onClick={() => setDetail(step)}>
                            查看动作原始证据
                          </Button>
                        </Space>
                      </>
                    ),
                  };
                })}
              />
            ),
          };
        })}
      />
      {!hops.length && <p>此路径未提供逐跳信息，保留引擎返回的路径结论。</p>}
      <DetailsDrawer
        open={detail !== undefined}
        title="路径动作原始证据"
        onClose={() => setDetail(undefined)}
        queryKey={[...queryKey, "step", identity, detail]}
        load={async () => detail}
      />
    </>
  );
}
