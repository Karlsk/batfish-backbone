import { describe, expect, it } from "vitest";
import type { components } from "../../../api/schema";
import { describeRun, prepareMvpCheck } from "./model";

type Run = components["schemas"]["CheckRun"];
type Result = components["schemas"]["ResultEnvelope"];

const base = {
  id: "run",
  template_id: "traceroute",
  status: "succeeded",
  snapshot_quality: {},
  jobs: [],
  result_ids: ["result"],
  effective_parameters: {
    request: { start_location: "r1", destination_ip: "10.0.0.2" },
  },
} as unknown as Run;

describe("leader MVP check model", () => {
  it("requires an explicit route or trace range before submission", () => {
    expect(() => prepareMvpCheck("routes", { network: "" })).toThrow(/网段/);
    expect(() => prepareMvpCheck("lpm-routes", { ip: "" })).toThrow(/地址/);
    expect(() =>
      prepareMvpCheck("traceroute", { start_location: "r1" }),
    ).toThrow(/目的/);
    expect(prepareMvpCheck("routes", { network: "10.0.0.0/24" }).scope).toEqual(
      { network: "10.0.0.0/24" },
    );
    expect(
      prepareMvpCheck("traceroute", {
        start_location: "r1",
        destination_ip: "10.0.0.2",
        protocol: "tcp",
        destination_port: 443,
      }).options,
    ).toEqual({ ip_protocols: ["tcp"], destination_ports: [443] });
  });

  it("does not convert incomplete, unknown or failed work into an empty success", () => {
    expect(describeRun({ ...base, status: "queued" }, null).headline).toMatch(
      /排队/,
    );
    expect(
      describeRun({ ...base, status: "failed", error_code: "NOT_READY" }, null)
        .headline,
    ).toMatch(/失败/);
    expect(
      describeRun(
        {
          ...base,
          status: "running",
          jobs: [{ engine_state: "unknown", phase: "engine_wait" }],
        } as Run,
        null,
      ).warnings,
    ).toContain("引擎状态待确认；不要重复提交检查。");
    expect(
      describeRun({ ...base, status: "result_unavailable" }, null).headline,
    ).toMatch(/暂不可读/);
  });

  it("reports only stored trace dispositions and keeps model limits visible", () => {
    const result = {
      kind: "traces",
      summary: {
        dispositions: { ACCEPTED: 1, NO_ROUTE: 1 },
        returned_trace_count: 2,
      },
      warnings: ["样本范围有限"],
      coverage: "limited",
      truncated: true,
      truncation_reason: "max traces",
    } as unknown as Result;
    const view = describeRun(base, result);
    expect(view.headline).toMatch(/已保存.*2/);
    expect(view.facts).toContain("已到达目标（ACCEPTED）：1 条");
    expect(view.facts).toContain("无匹配路由（NO_ROUTE）：1 条");
    expect(view.warnings).toContain(
      "仅为单向配置模型推演，不证明在线转发或回程。",
    );
    expect(view.warnings.some((item) => item.includes("截断"))).toBe(true);
    expect(view.headline).not.toMatch(/全部可达/);
  });

  it("shows configuration parsing warnings at the conclusion level", () => {
    const quality = describeRun(
      {
        ...base,
        template_id: "configuration-quality",
        result_ids: [],
        snapshot_quality: {
          node_count: 2,
          issue_count: 1,
          parse_statuses: ["PARTIALLY_UNRECOGNIZED"],
          model_limits: [{ capability: "ipv6" }],
        },
      },
      null,
    );
    expect(quality.headline).toMatch(/解析.*问题/);
    expect(quality.warnings.some((item) => item.includes("模型限制"))).toBe(
      true,
    );
  });
});
