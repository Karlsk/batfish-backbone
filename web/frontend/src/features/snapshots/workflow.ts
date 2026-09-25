import type { components } from "../../api/schema";
type Upload = components["schemas"]["UploadDTO"];
type Created = components["schemas"]["SnapshotCreated"];
type Options = components["schemas"]["InitializationOptions"];
export type UploadMode = "files" | "archive";
type Adapter = {
  upload: (
    networkId: string,
    files: File[],
    mode: UploadMode,
  ) => Promise<Upload>;
  initialize: (
    networkId: string,
    body: components["schemas"]["CreateSnapshotRequest"],
    key: string,
  ) => Promise<Created>;
};
export class UploadWorkflow {
  private uploaded: Upload | null = null;
  private pending: Promise<Created> | null = null;
  private completed: Created | null = null;
  private frozen: string | null = null;
  private readonly key = crypto.randomUUID();
  constructor(
    readonly networkId: string,
    private readonly adapter: Adapter,
  ) {}
  get attempted() {
    return this.frozen !== null;
  }
  async upload(files: File[], mode: UploadMode) {
    if (this.attempted) throw new Error("Initialization already submitted");
    this.uploaded = null;
    const uploaded = await this.adapter.upload(this.networkId, files, mode);
    this.uploaded = uploaded;
    return uploaded;
  }
  async initialize(name: string, options: Options): Promise<Created> {
    if (!this.uploaded) throw new Error("Upload required");
    const body = { display_name: name, upload_id: this.uploaded.id, options };
    const serialized = JSON.stringify(body);
    if (this.frozen !== null && this.frozen !== serialized)
      throw new Error("Parameters are frozen");
    if (this.completed) return this.completed;
    if (this.pending) return this.pending;
    this.frozen = serialized;
    this.pending = this.adapter.initialize(this.networkId, body, this.key);
    try {
      this.completed = await this.pending;
      return this.completed;
    } finally {
      this.pending = null;
    }
  }
}
