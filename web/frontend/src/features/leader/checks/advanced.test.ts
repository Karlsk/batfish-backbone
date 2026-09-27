import { describe, expect, it } from "vitest";
import type { components } from "../../../api/schema";
import { describeAdvanced, prepareAdvancedCheck } from "./advanced";

type Result = components["schemas"]["ResultEnvelope"];

const result = (summary: Record<string, unknown> = {}) =>
  ({
    summary,
    coverage: "complete",
    truncated: false,
    warnings: [],
  }) as unknown as Result;

describe("leader ADV guided checks", () => {
  it("requires an explicit ACL flow and filter scope", () => {
    expect(() => prepareAdvancedCheck("acl", {})).toThrow(/源地址/);
    expect(() =>
      prepareAdvancedCheck("acl", {
        source_ip: "10.0.0.1",
        destination_ip: "10.0.0.2",
      }),
    ).toThrow(/ACL/);
    expect(
      prepareAdvancedCheck("acl", {
        source_ip: "10.0.0.1",
        destination_ip: "10.0.0.2",
        filters: "acl-in",
        protocol: "tcp",
        destination_port: 443,
      }),
    ).toEqual({
      scope: {
        source_ip: "10.0.0.1",
        destination_ip: "10.0.0.2",
        filters: { mode: "literal", values: ["acl-in"] },
      },
      options: { ip_protocols: ["tcp"], destination_ports: [443] },
    });
  });

  it("preserves topology view, BGP mode and bounded device scopes", () => {
    expect(
      prepareAdvancedCheck("topology", {
        view: "bgp",
        nodes: "c1, c2",
      }).options,
    ).toEqual({
      view: "bgp",
      nodes: { mode: "literal", values: ["c1", "c2"] },
    });
    expect(
      prepareAdvancedCheck("bgp", { mode: "compatibility" }).options,
    ).toEqual({ mode: "compatibility" });
    expect(() =>
      prepareAdvancedCheck("topology", {
        nodes: Array(101).fill("c1").join(","),
      }),
    ).toThrow(/100/);
  });

  it("labels saved graph provenance without asserting physical connectivity", () => {
    const view = describeAdvanced(
      "topology",
      result({ returned_nodes: 4, returned_edges: 3, edge_type: "layer3" }),
    );
    expect(view.headline).toMatch(/4 台.*3 条/);
    expect(view.warnings.join(" ")).toMatch(/推导.*物理/);
    expect(view.facts.join(" ")).toMatch(/三层推导.*配置模型/);
  });

  it("keeps BGP model status separate from live session health and paging", () => {
    const view = describeAdvanced("bgp", result(), {
      rows: [
        { Established_Status: "ESTABLISHED" },
        { Established_Status: "NOT_ESTABLISHED" },
      ],
      total: 3,
      truncated: false,
    });
    expect(view.headline).toMatch(/模型会话/);
    expect(view.facts.join(" ")).toMatch(/前 2 条/);
    expect(view.warnings.join(" ")).toMatch(/不代表.*实时/);
    expect(view.headline).not.toMatch(/健康/);
  });

  it("distinguishes ACL permit, explicit deny, implicit deny and no match", () => {
    const permit = describeAdvanced("acl", result(), {
      rows: [{ Action: "PERMIT" }],
      total: 1,
      truncated: false,
    });
    expect(permit.headline).toMatch(/局部放行/);
    const deny = describeAdvanced("acl", result(), {
      rows: [{ Action: "DENY", Implicit_Deny: false }],
      total: 1,
      truncated: false,
    });
    expect(deny.headline).toMatch(/ACL 拒绝/);
    const implicit = describeAdvanced("acl", result(), {
      rows: [{ Action: "DENY", Implicit_Deny: true }],
      total: 1,
      truncated: false,
    });
    expect(implicit.headline).toMatch(/隐式拒绝/);
    const empty = describeAdvanced("acl", result(), {
      rows: [],
      total: 0,
      truncated: false,
    });
    expect(empty.headline).toMatch(/没有匹配.*无法判断/);
    expect(permit.warnings.join(" ")).toMatch(/不代表端到端/);
  });

  it("never treats truncated evidence as a complete ACL or BGP conclusion", () => {
    const view = describeAdvanced("acl", result(), {
      rows: [{ Action: "PERMIT" }],
      total: 3,
      truncated: true,
    });
    expect(view.headline).toMatch(/分页|无法判断/);
    expect(view.warnings.join(" ")).toMatch(/截断/);
  });
});
