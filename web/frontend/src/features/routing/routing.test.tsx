import { it, expect } from "vitest";
import { buildRequest, defaultDraft, selectorValue } from "./requests";
import { resourceKey } from "../../app/context";
it("routes exact prefix and LPM address are distinct typed requests", () => {
  const draft = { ...defaultDraft(), destination: "10.0.0.0/24" };
  expect(buildRequest("routes", draft)).toMatchObject({
    options: { network: "10.0.0.0/24", prefix_match_type: "EXACT" },
  });
  expect(() => buildRequest("lpm-routes", draft)).toThrow();
  expect(
    buildRequest("lpm-routes", { ...draft, destination: "10.0.0.1" }),
  ).toEqual({ ip: "10.0.0.1", nodes: null, options: { vrfs: null } });
  expect(() =>
    buildRequest("routes", { ...draft, destination: "10.0.0.1/24" }),
  ).toThrow();
});
it("literal selections never silently become expert expressions", () => {
  expect(selectorValue("literal", ["a.*"], "ignored")).toEqual({
    mode: "literal",
    values: ["a.*"],
  });
  expect(selectorValue("expression", ["ignored"], "/r.*/")).toEqual({
    mode: "expression",
    expression: "/r.*/",
  });
});
it("snapshot, result, filter and page identify separate result queries", () => {
  const key = (s: string, id: string, filter: string, offset: number) =>
    resourceKey(
      "u",
      { networkId: "n", snapshotId: s },
      "rows",
      { filter, offset },
      id,
    );
  const baseline = key("s", "a", "", 0);
  for (const other of [
    key("other", "a", "", 0),
    key("s", "b", "", 0),
    key("s", "a", "r1", 0),
    key("s", "a", "", 20),
  ])
    expect(other).not.toEqual(baseline);
});
