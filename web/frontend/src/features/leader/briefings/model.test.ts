import { describe, expect, it } from "vitest";
import {
  briefingIndicators,
  readableWarning,
  reportableRuns,
  selectedSources,
  summaryFacts,
  type RunPick,
} from "./model";

const run = (id: string, overrides: Partial<RunPick> = {}): RunPick => ({
  id,
  template_id: "devices",
  status: "succeeded",
  snapshot_id: "snapshot-a",
  result_ids: [`result-${id}`],
  effective_parameters: {},
  concern_id: null,
  concern_version: null,
  ...overrides,
});

describe("fixed briefing source selection", () => {
  it("offers only completed results from the chosen snapshot", () => {
    expect(
      reportableRuns(
        [
          run("ok"),
          run("queued", { status: "queued" }),
          run("empty", { result_ids: [] }),
          run("other", { snapshot_id: "snapshot-b" }),
        ],
        "snapshot-a",
      ).map((item) => item.id),
    ).toEqual(["ok"]);
  });

  it("keeps one fixed comparison and one matching concern version", () => {
    const selected = selectedSources([
      run("a", {
        effective_parameters: { comparison_id: "comparison-a" },
        concern_id: "concern-a",
        concern_version: 2,
      }),
      run("b", {
        effective_parameters: { comparison_id: "comparison-a" },
        concern_id: "concern-a",
        concern_version: 2,
      }),
    ]);
    expect(selected).toEqual({
      resultIds: ["result-a", "result-b"],
      comparisonId: "comparison-a",
      concernId: "concern-a",
      concernVersion: 2,
    });
    expect(() =>
      selectedSources([
        run("a", {
          effective_parameters: { comparison_id: "comparison-a" },
        }),
        run("b", {
          effective_parameters: { comparison_id: "comparison-b" },
        }),
      ]),
    ).toThrow(/不同的固定比较/);
    expect(
      selectedSources([
        run("bound", { concern_id: "concern-a", concern_version: 2 }),
        run("unbound"),
      ]).concernId,
    ).toBeNull();
  });
});

describe("meeting facts", () => {
  it("renders structured capability limitations as readable text without losing the description", () => {
    expect(
      readableWarning(
        "{'vendor': 'HUAWEI_VRP', 'capability': 'ipv6', 'status': 'unsupported', 'description': '仅验证 IPv4'}",
      ),
    ).toBe("HUAWEI_VRP · ipv6：未支持；仅验证 IPv4");
    expect(readableWarning("普通模型警告")).toBe("普通模型警告");
  });
  it("summarizes known counts without treating limited evidence as healthy", () => {
    expect(summaryFacts({ added: 2, removed: 1, changed: 3 })).toEqual([
      { label: "新增", value: "2" },
      { label: "消失", value: "1" },
      { label: "变化", value: "3" },
    ]);
    expect(
      briefingIndicators({
        coverage: "limited",
        truncated: true,
        truncation_reason: "row_limit",
        warnings: ["MODEL_LIMIT"],
      }),
    ).toEqual(["模型覆盖有限", "结果已截断：row_limit", "MODEL_LIMIT"]);
  });
});
