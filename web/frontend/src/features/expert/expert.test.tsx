import { expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigProvider } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { components } from "../../api/schema";
import { ExpertForm } from "./ExpertForm";
import { buildExpertParameters, effectiveExpertParameters } from "./model";

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../../api/client", async (original) => ({
  ...(await original<typeof import("../../api/client")>()),
  api: { GET: mocks.get, POST: mocks.post },
}));
vi.mock("../../components/useDraftGuard", () => ({
  useDraftGuard: () => ({ holder: null, allowNavigation: () => {} }),
}));

const capability = {
  id: "lpm-routes",
  label: "Longest prefix match",
  stage: 1,
  enabled: true,
  disabled_reason: null,
  required_fields: ["ip"],
  parameters_schema: {
    type: "object",
    properties: {
      ip: { type: "string", title: "IP" },
      nodes: { anyOf: [{ $ref: "#/$defs/LiteralSelector" }, { type: "null" }] },
      options: { $ref: "#/$defs/LpmOptions" },
    },
    required: ["ip"],
    additionalProperties: false,
  },
  options_schema: {
    type: "object",
    properties: { vrfs: {} },
    additionalProperties: false,
  },
  defaults: { options: {} },
  result_kind: "table",
  requires_dataplane: true,
  schema_version: "1",
} as components["schemas"]["Capability"];

it("builds typed basic fields and preserves a valid advanced options object", () => {
  expect(
    buildExpertParameters(capability, {
      fields: { ip: "10.64.0.4", nodes: '{"mode":"literal","values":["c1"]}' },
      optionsText: '{"vrfs":{"mode":"literal","values":["default"]}}',
    }),
  ).toEqual({
    ip: "10.64.0.4",
    nodes: { mode: "literal", values: ["c1"] },
    options: { vrfs: { mode: "literal", values: ["default"] } },
  });
  expect(() =>
    buildExpertParameters(capability, {
      fields: { ip: "10.64.0.4" },
      optionsText: '{"vrfs":',
    }),
  ).toThrow("options");
});

it("shows server defaults in the effective preview after clearing explicit options", () => {
  const withDefaults = {
    ...capability,
    defaults: { options: { vrfs: null } },
  } as components["schemas"]["Capability"];
  expect(
    effectiveExpertParameters(withDefaults, {
      fields: { ip: "10.64.0.4" },
      optionsText: "{}",
    }),
  ).toEqual({ ip: "10.64.0.4", options: { vrfs: null } });
});

it("keeps invalid JSON text and shows active expert conditions in basic view", async () => {
  mocks.get.mockResolvedValue({
    data: [capability],
    response: new Response("{}"),
  });
  const user = userEvent.setup();
  const { container } = render(
    <ConfigProvider button={{ autoInsertSpace: false }}>
      <MemoryRouter>
        <QueryClientProvider
          client={
            new QueryClient({ defaultOptions: { queries: { retry: false } } })
          }
        >
          <ExpertForm networkId="network" snapshotId="snapshot" />
        </QueryClientProvider>
      </MemoryRouter>
    </ConfigProvider>,
  );
  await user.click(await screen.findByRole("combobox", { name: "专家能力" }));
  await user.click(
    screen.getByRole("option", { name: /Longest prefix match/ }),
  );
  await user.type(screen.getByRole("textbox", { name: "IP" }), "10.64.0.4");
  await user.click(screen.getByRole("button", { name: /高级参数/ }));
  const options = screen.getByRole("textbox", {
    name: "专家 options JSON",
  }) as HTMLTextAreaElement;
  fireEvent.change(options, { target: { value: '{"vrfs":' } });
  await user.click(screen.getByRole("button", { name: "运行专家查询" }));
  expect(options.value).toBe('{"vrfs":');
  expect(screen.getByText(/options JSON 格式错误/)).toBeTruthy();
  expect(mocks.post).not.toHaveBeenCalled();
  fireEvent.change(options, {
    target: { value: '{"vrfs":{"mode":"literal","values":["default"]}}' },
  });
  expect(screen.queryByText(/options JSON 格式错误/)).toBeNull();
  await waitFor(() =>
    expect(container.querySelector("pre.raw-detail")?.textContent).toContain(
      '"vrfs"',
    ),
  );
});
