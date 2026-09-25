import { it, expect, vi } from "vitest";
const options = { ignore_management_interfaces: true, parse_reuse: false };
import { UploadWorkflow } from "./workflow";
it("failed upload never initializes and retry keeps its network", async () => {
  const upload = vi
    .fn()
    .mockRejectedValueOnce(new Error("invalid"))
    .mockResolvedValue({ id: "upload" });
  const initialize = vi.fn();
  const workflow = new UploadWorkflow("network-a", { upload, initialize });
  await expect(
    workflow.upload([new File(["x"], "r.cfg")], "files"),
  ).rejects.toThrow("invalid");
  await expect(workflow.initialize("snapshot", options)).rejects.toThrow(
    "Upload required",
  );
  expect(initialize).not.toHaveBeenCalled();
  await workflow.upload([new File(["x"], "r.cfg")], "files");
  expect(upload.mock.calls.map((call) => call[0])).toEqual([
    "network-a",
    "network-a",
  ]);
});
it("duplicate initialization shares one request and stable idempotency key on retry", async () => {
  let finish!: (value: unknown) => void;
  const initialize = vi
    .fn()
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    )
    .mockRejectedValueOnce(new Error("network"))
    .mockResolvedValue({ snapshot_id: "s", job_id: "j" });
  const workflow = new UploadWorkflow("n", {
    upload: vi.fn().mockResolvedValue({ id: "u" }),
    initialize,
  });
  await workflow.upload([new File(["x"], "r")], "files");
  const first = workflow.initialize("name", options);
  const duplicate = workflow.initialize("name", options);
  expect(initialize).toHaveBeenCalledTimes(1);
  finish({ snapshot_id: "s", job_id: "j" });
  await Promise.all([first, duplicate]);
  expect(initialize).toHaveBeenCalledTimes(1);
});
it("uncertain initialization retries reuse key and frozen parameters", async () => {
  const initialize = vi
    .fn()
    .mockRejectedValueOnce(new Error("connection"))
    .mockResolvedValue({ snapshot_id: "s", job_id: "j" });
  const workflow = new UploadWorkflow("n", {
    upload: vi.fn().mockResolvedValue({ id: "u" }),
    initialize,
  });
  await workflow.upload([new File(["x"], "r")], "files");
  await expect(workflow.initialize("name", options)).rejects.toThrow();
  await expect(workflow.initialize("changed", options)).rejects.toThrow(
    "Parameters are frozen",
  );
  await workflow.initialize("name", options);
  expect(initialize.mock.calls[0][2]).toBe(initialize.mock.calls[1][2]);
});
