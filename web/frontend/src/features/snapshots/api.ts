import { api, unwrap } from "../../api/client";
import type { UploadMode } from "./workflow";
export const uploadAdapter = {
  upload: (networkId: string, files: File[], mode: UploadMode) =>
    unwrap(
      api.POST("/api/v1/networks/{network_id}/uploads", {
        params: { path: { network_id: networkId } },
        body: mode === "archive" ? { archive: files[0] } : { files },
        bodySerializer: () => {
          const form = new FormData();
          files.forEach((file) =>
            form.append(
              mode === "archive" ? "archive" : "files",
              file,
              file.name,
            ),
          );
          return form;
        },
      }),
    ),
  initialize: (
    networkId: string,
    body: import("../../api/schema").components["schemas"]["CreateSnapshotRequest"],
    key: string,
  ) =>
    unwrap(
      api.POST("/api/v1/networks/{network_id}/snapshots", {
        params: {
          path: { network_id: networkId },
          header: { "idempotency-key": key },
        },
        body,
      }),
    ),
};
