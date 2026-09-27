import { describe, expect, it } from "vitest";
import type { components } from "../../../api/schema";
import {
  changeConclusion,
  canCompareDerived,
  prepareChangeCheck,
  prepareFaultCheck,
  relevantConcern,
} from "./model";

type Result = components["schemas"]["ResultEnvelope"];
const result = (operation: string, summary: Record<string, unknown>) =>
  ({
    kind: operation === "change-config" ? "diff" : "table",
    summary,
    coverage: "complete",
    warnings: [],
    truncated: false,
  }) as unknown as Result;

describe("leader fixed change and fault semantics", () => {
  it("requires a fixed comparison and explicit route/flow range", () => {
    expect(() =>
      prepareChangeCheck("change-config", { comparison_id: "" }),
    ).toThrow(/比较/);
    expect(() =>
      prepareChangeCheck("change-routes", { comparison_id: "id" }),
    ).toThrow(/网段/);
    expect(() =>
      prepareChangeCheck("change-reachability", {
        comparison_id: "id",
        start_location: "c1",
      }),
    ).toThrow(/目的/);
    expect(
      prepareChangeCheck("change-routes", {
        comparison_id: "id",
        network: "10.64.0.0/24",
      }),
    ).toEqual({
      scope: { comparison_id: "id", network: "10.64.0.0/24" },
      options: {},
    });
  });

  it("keeps direction and protocol in the frozen reachability scope", () => {
    expect(
      prepareChangeCheck("change-reachability", {
        comparison_id: "fixed",
        start_location: "c1",
        destination_ips: "10.64.0.4",
        protocol: "tcp",
        destination_port: 443,
      }),
    ).toEqual({
      scope: {
        comparison_id: "fixed",
        start_location: "c1",
        destination_ips: "10.64.0.4",
      },
      options: { ip_protocols: ["tcp"], destination_ports: [443] },
    });
  });

  it("requires a named and explicitly selected fault target", () => {
    expect(() => prepareFaultCheck({ display_name: "test" })).toThrow(
      /设备或一个接口/,
    );
    expect(
      prepareFaultCheck({
        display_name: "c2 离线模拟",
        nodes: "c2",
      }).scope,
    ).toEqual({
      display_name: "c2 离线模拟",
      deactivate_nodes: ["c2"],
      deactivate_interfaces: [],
    });
  });

  it("counts only saved scoped differences and never claims whole-network equivalence", () => {
    const config = changeConclusion(
      "change-config",
      result("change-config", { total_files: 2, added: 1, removed: 1 }),
    );
    expect(config.headline).toMatch(/2 个配置文件/);
    expect(config.facts.join(" ")).toMatch(/候选新增.*基线消失/);
    const empty = changeConclusion(
      "change-routes",
      result("change-routes", { returned_rows: 0 }),
    );
    expect(empty.headline).toMatch(/所选范围.*未返回/);
    expect(empty.warnings.join(" ")).toMatch(/不代表全网/);
  });

  it("does not turn sampled reachability witnesses into business impact", () => {
    const view = changeConclusion(
      "change-reachability",
      result("change-reachability", {
        returned_examples: 2,
        count_scope: "sdk_witness_rows_not_all_business_flows",
        changes: { INCREASED: 1, DECREASED: 1 },
      }),
    );
    expect(view.headline).toMatch(/2 条.*样本/);
    expect(view.warnings.join(" ")).toMatch(/不能推断全部业务/);
    expect(view.headline).not.toMatch(/业务中断/);
  });

  it("shows concern mapping only for the exact frozen flow", () => {
    const concern = {
      id: "c",
      version: 4,
      flows: [
        {
          start_location: "c1",
          destination_ip: "10.64.0.4",
          source_ip: "10.64.0.1",
        },
      ],
    } as unknown as components["schemas"]["ConcernDTO"];
    expect(
      relevantConcern(concern, "c1", "10.64.0.4", undefined, null, "10.64.0.1"),
    ).toBe(true);
    expect(
      relevantConcern(concern, "c1", "10.64.0.4", undefined, null, "10.64.0.9"),
    ).toBe(false);
    expect(relevantConcern(concern, "c1", "10.64.0.3")).toBe(false);
  });

  it("opens fault comparison only for a succeeded job and a ready derived snapshot", () => {
    expect(canCompareDerived("succeeded", "ready")).toBe(true);
    expect(canCompareDerived("succeeded", "ready_with_warnings")).toBe(true);
    expect(canCompareDerived("succeeded", "failed")).toBe(false);
    expect(canCompareDerived("running", "ready")).toBe(false);
    expect(canCompareDerived("interrupted", "ready")).toBe(false);
  });
});
