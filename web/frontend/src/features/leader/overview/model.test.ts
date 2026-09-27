import { describe, expect, it } from "vitest";
import { describeNetwork } from "./model";
import type { components } from "../../../api/schema";

type Card = components["schemas"]["NetworkOverview"];
const card = (change: Partial<Card>): Card => ({
  network_id: "network",
  display_name: "业务网络",
  sync_state: "ready",
  readiness: "pending",
  check_state: "not_checked",
  concern_count: 0,
  latest_snapshot: null,
  latest_ready_snapshot: null,
  latest_job: null,
  latest_result: null,
  ...change,
});

describe("leader overview language", () => {
  it("does not turn an unchecked network into a healthy conclusion", () => {
    const view = describeNetwork(card({}));
    expect(view.readiness).toBe("待准备");
    expect(view.check).toBe("未检查");
    expect(view.tone).not.toBe("good");
  });

  it("keeps limited and truncated result warnings visible beside a later interrupted job", () => {
    const view = describeNetwork(
      card({
        readiness: "warning",
        check_state: "interrupted",
        latest_result: {
          id: "result",
          snapshot_id: "snapshot",
          coverage: "limited",
          truncated: true,
          truncation_reason: "row_limit",
          warning_count: 2,
          created_at: "2026-09-28T00:00:00Z",
        },
      }),
    );
    expect(view.check).toBe("检查中断");
    expect(view.warnings).toEqual(
      expect.arrayContaining(["覆盖有限", "结果已截断", "2 条结果警告"]),
    );
    expect(view.tone).toBe("warning");
  });
});
