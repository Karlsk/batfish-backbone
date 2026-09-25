import { useEffect, useRef, useState, useCallback } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  Modal,
  Radio,
  Space,
  Steps,
  Table,
} from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useBlocker, useBeforeUnload } from "react-router-dom";
import { api, unwrap, ApiError } from "../../api/client";
import {
  useResourceContext,
  resourceKey,
  type Selection,
} from "../../app/context";
import { useSession } from "../../app/session";
import { ErrorState } from "../../components/States";
import { AdvancedOptions } from "../../components/AdvancedOptions";
import { UploadWorkflow, type UploadMode } from "./workflow";
import { uploadAdapter } from "./api";
import type { components } from "../../api/schema";
export function UploadWizard({ network }: { network: Selection }) {
  const session = useSession();
  const { registerGuard } = useResourceContext();
  const client = useQueryClient();
  const [modal, modalHolder] = Modal.useModal();
  const [workflow, setWorkflow] = useState(
    () => new UploadWorkflow(network.id, uploadAdapter),
  );
  const [mode, setMode] = useState<UploadMode>("files");
  const [files, setFiles] = useState<File[]>([]);
  const [upload, setUpload] = useState<
    components["schemas"]["UploadDTO"] | null
  >(null);
  const [created, setCreated] = useState<
    components["schemas"]["SnapshotCreated"] | null
  >(null);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [name, setName] = useState("");
  const [ignoreManagement, setIgnoreManagement] = useState(true);
  const [parseReuse, setParseReuse] = useState(false);
  const alive = useRef(true);
  const inFlight = useRef(false);
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  const limits = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: network.id, snapshotId: null },
      "upload-limits",
    ),
    queryFn: () => unwrap(api.GET("/api/v1/upload-limits")),
  });
  const dirty = files.length > 0 && !created;
  const confirmDiscard = useCallback(
    () =>
      new Promise<boolean>((resolve) => {
        if (inFlight.current) {
          modal.info({
            title: "操作仍在进行",
            content: "请等待当前请求结束后再离开。",
          });
          resolve(false);
          return;
        }
        modal.confirm({
          title: "放弃未完成的快照向导？",
          content: attempted
            ? "初始化请求可能已被服务端接收，请先查看快照列表确认状态。"
            : "离开将清空本次文件选择与填写内容。",
          okText: "放弃并切换",
          cancelText: "继续填写",
          onOk: () => {
            setFiles([]);
            setUpload(null);
            setName("");
            setIgnoreManagement(true);
            setParseReuse(false);
            setError(undefined);
            setAttempted(false);
            setWorkflow(new UploadWorkflow(network.id, uploadAdapter));
            if (fileInput.current) fileInput.current.value = "";
            resolve(true);
          },
          onCancel: () => resolve(false),
        });
      }),
    [modal, attempted, network.id],
  );
  useEffect(() => {
    if (dirty) return registerGuard(confirmDiscard);
  }, [dirty, registerGuard, confirmDiscard]);
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      !!dirty &&
      (currentLocation.pathname !== nextLocation.pathname ||
        currentLocation.search !== nextLocation.search),
  );
  const confirming = useRef(false);
  useEffect(() => {
    if (blocker.state !== "blocked") {
      confirming.current = false;
      return;
    }
    if (confirming.current) return;
    confirming.current = true;
    void confirmDiscard().then((allowed) => {
      if (allowed) blocker.proceed();
      else blocker.reset();
    });
  }, [blocker, confirmDiscard]);
  useBeforeUnload(
    useCallback(
      (event) => {
        if (dirty) {
          event.preventDefault();
          event.returnValue = "";
        }
      },
      [dirty],
    ),
  );
  const uploadFiles = async () => {
    if (inFlight.current || !files.length || !limits.data) return;
    inFlight.current = true;
    setBusy(true);
    setError(undefined);
    try {
      if (
        files.length > limits.data.max_files ||
        files.reduce((n, f) => n + f.size, 0) > limits.data.max_bytes
      )
        throw new ApiError("UPLOAD_TOO_LARGE");
      if (mode === "archive" && files.length !== 1)
        throw new ApiError("VALIDATION_ERROR");
      const data = await workflow.upload(files, mode);
      if (alive.current) setUpload(data);
    } catch (e) {
      if (alive.current) setError(e);
    } finally {
      inFlight.current = false;
      if (alive.current) setBusy(false);
    }
  };
  return (
    <Card title="创建快照" className="upload-wizard">
      {modalHolder}
      <Steps
        current={created ? 3 : upload ? 2 : files.length ? 1 : 0}
        size="small"
        items={[
          { title: "选择配置" },
          { title: "上传与校验" },
          { title: "填写快照" },
          { title: "提交初始化" },
        ]}
      />
      <p className="muted">
        目标网络：{network.name} · {network.id.slice(0, 8)}
      </p>
      {limits.isError ? (
        <ErrorState error={limits.error} retry={() => void limits.refetch()} />
      ) : (
        limits.data && (
          <Alert
            type="info"
            title={`服务端限额：最多 ${limits.data.max_files} 个文件，上传 ${(limits.data.max_bytes / 1048576).toFixed(1)} MiB，ZIP解压后 ${(limits.data.max_expanded_bytes / 1048576).toFixed(1)} MiB。`}
            showIcon
          />
        )
      )}
      {!!error && (
        <>
          <ErrorState error={error} />
          {error instanceof ApiError && error.fieldErrors.length > 0 && (
            <ul>
              {error.fieldErrors.map((field, index) => (
                <li key={index}>
                  {field.path.join(".")}：{field.message}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {created ? (
        <Alert
          type="success"
          showIcon
          title="初始化任务已提交"
          description={
            <>
              <p>上传成功不代表初始化完成；请在下方快照列表查看实际状态。</p>
              <Link to={`/jobs/${created.job_id}`}>查看初始化任务</Link>
              <div className="record-id">任务编号：{created.job_id}</div>
              <Button
                onClick={() => {
                  setFiles([]);
                  setUpload(null);
                  setCreated(null);
                  setName("");
                  setAttempted(false);
                  setIgnoreManagement(true);
                  setParseReuse(false);
                  setWorkflow(new UploadWorkflow(network.id, uploadAdapter));
                }}
              >
                创建另一份快照
              </Button>
            </>
          }
        />
      ) : (
        <>
          {!upload && (
            <>
              <Radio.Group
                value={mode}
                disabled={busy}
                onChange={(event) => {
                  setMode(event.target.value);
                  setFiles([]);
                  setError(undefined);
                  if (fileInput.current) fileInput.current.value = "";
                }}
                options={[
                  { value: "files", label: "配置文件" },
                  { value: "archive", label: "ZIP压缩包" },
                ]}
              />
              <label className="file-picker">
                {mode === "files" ? "选择配置文件" : "选择ZIP文件"}
                <input
                  ref={fileInput}
                  aria-label={mode === "files" ? "选择配置文件" : "选择ZIP文件"}
                  type="file"
                  multiple={mode === "files"}
                  accept={mode === "archive" ? ".zip" : undefined}
                  disabled={busy}
                  onChange={(event) =>
                    setFiles(Array.from(event.target.files ?? []))
                  }
                />
              </label>
              <p>
                {files.length
                  ? `已选择 ${files.length} 个文件`
                  : "配置文件会按原始文件名提交；ZIP需包含configs目录。"}
              </p>
              <Button
                type="primary"
                disabled={!files.length || !limits.data}
                loading={busy}
                onClick={() => void uploadFiles()}
              >
                上传并校验
              </Button>
            </>
          )}
          {upload && (
            <>
              <Alert
                type="success"
                showIcon
                title={`文件校验完成，共 ${upload.manifest.files.length} 个文件；尚未初始化。`}
              />
              <details>
                <summary>查看已校验文件</summary>
                <Table
                  size="small"
                  rowKey="id"
                  dataSource={upload.manifest.files}
                  pagination={{ pageSize: 10, showSizeChanger: false }}
                  columns={[
                    { title: "文件", dataIndex: "path" },
                    { title: "字节数", dataIndex: "size_bytes" },
                    { title: "编码", dataIndex: "encoding" },
                  ]}
                />
              </details>
              <Form
                layout="vertical"
                onFinish={async () => {
                  if (inFlight.current) return;
                  inFlight.current = true;
                  setBusy(true);
                  setAttempted(true);
                  setError(undefined);
                  try {
                    const result = await workflow.initialize(name, {
                      ignore_management_interfaces: ignoreManagement,
                      parse_reuse: parseReuse,
                    });
                    if (alive.current) {
                      setCreated(result);
                      await client.invalidateQueries({
                        predicate: (q) =>
                          q.queryKey[2] === network.id &&
                          q.queryKey[5] === "snapshots",
                      });
                    }
                  } catch (e) {
                    if (alive.current) setError(e);
                  } finally {
                    inFlight.current = false;
                    if (alive.current) setBusy(false);
                  }
                }}
              >
                <Form.Item label="快照名称" required>
                  <Input
                    aria-label="快照名称"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    disabled={attempted}
                    maxLength={255}
                  />
                </Form.Item>
                <AdvancedOptions
                  activeCount={Number(!ignoreManagement) + Number(parseReuse)}
                >
                  <Space orientation="vertical">
                    <Checkbox
                      checked={ignoreManagement}
                      disabled={attempted}
                      onChange={(event) =>
                        setIgnoreManagement(event.target.checked)
                      }
                    >
                      忽略管理接口
                    </Checkbox>
                    <Checkbox
                      checked={parseReuse}
                      disabled={attempted}
                      onChange={(event) => setParseReuse(event.target.checked)}
                    >
                      允许复用解析缓存
                    </Checkbox>
                  </Space>
                </AdvancedOptions>
                <Button
                  type="primary"
                  htmlType="submit"
                  disabled={!name.trim()}
                  loading={busy}
                >
                  {attempted ? "重试初始化" : "提交初始化"}
                </Button>
                {attempted && (
                  <p className="muted">
                    请求参数已固定，重试会复用同一请求编号。
                  </p>
                )}
              </Form>
            </>
          )}
        </>
      )}
    </Card>
  );
}
