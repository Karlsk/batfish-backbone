import { useEffect, useMemo, useRef } from "react";
import { Button, Space, theme } from "antd";
import cytoscape, { type Core } from "cytoscape";
import { prepareGraph, type Graph, type GraphSelection } from "./model";
export function GraphCanvas({
  graph,
  onSelect,
}: {
  graph: Graph;
  onSelect: (selection: GraphSelection) => void;
}) {
  const container = useRef<HTMLDivElement>(null),
    current = useRef<Core | null>(null),
    select = useRef(onSelect);
  select.current = onSelect;
  const { token } = theme.useToken();
  const elements = useMemo(() => prepareGraph(graph).elements, [graph]);
  useEffect(() => {
    const cy = cytoscape({
      container: container.current!,
      elements,
      layout: { name: "circle", padding: 48 },
      minZoom: 0.2,
      maxZoom: 3,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": token.colorPrimary,
            color: token.colorText,
            "font-size": 12,
            "text-valign": "bottom",
            "text-margin-y": 8,
            "text-wrap": "ellipsis",
            "text-max-width": "160px",
            width: 32,
            height: 32,
          },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": token.colorTextSecondary,
            "target-arrow-color": token.colorTextSecondary,
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            color: token.colorTextSecondary,
            "font-size": 10,
            "text-background-color": token.colorBgContainer,
            "text-background-opacity": 0.9,
            "text-background-padding": "2px",
            "control-point-step-size": 36,
          },
        },
        {
          selector: ":selected",
          style: {
            "overlay-color": token.colorPrimary,
            "overlay-opacity": 0.2,
            "overlay-padding": 8,
          },
        },
      ],
    });
    current.current = cy;
    cy.on("tap", "node", (event) =>
      select.current({ kind: "node", id: event.target.data("rawId") }),
    );
    cy.on("tap", "edge", (event) =>
      select.current({ kind: "edge", id: event.target.data("rawId") }),
    );
    const observer = new ResizeObserver(() => cy.resize());
    observer.observe(container.current!);
    return () => {
      observer.disconnect();
      cy.destroy();
      current.current = null;
    };
  }, [
    elements,
    token.colorPrimary,
    token.colorText,
    token.colorTextSecondary,
    token.colorBgContainer,
  ]);
  return (
    <>
      <Space className="filter-bar">
        <Button onClick={() => current.current?.fit(undefined, 48)}>
          适应画布
        </Button>
        <span className="muted">拖动仅调整布局；下方列表支持键盘操作。</span>
      </Space>
      <div
        ref={container}
        className="topology-canvas"
        role="img"
        aria-label="配置模型关系图"
      />
    </>
  );
}
