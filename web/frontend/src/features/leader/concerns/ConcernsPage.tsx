import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Tag,
  Typography,
} from "antd";
import { PlusOutlined, ArrowRightOutlined } from "@ant-design/icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, ApiError, unwrap } from "../../../api/client";
import type { components } from "../../../api/schema";
import { resourceKey, useResourceContext } from "../../../app/context";
import { useSession } from "../../../app/session";
import { AdvancedOptions } from "../../../components/AdvancedOptions";
import { ErrorState } from "../../../components/States";
import { useNetworks } from "../../networks/queries";
import { prepareConcern, type ConcernDraft } from "./draft";

type Concern = components["schemas"]["ConcernDTO"];
const priorityLabels = { high: "高", medium: "中", low: "低" };
const priorityColors = { high: "red", medium: "gold", low: "blue" };
const protocols = [
  "icmp",
  "tcp",
  "udp",
  "gre",
  "esp",
  "ah",
  "ospf",
  "sctp",
  "ipinip",
];

export function ConcernsPage() {
  const { network, selectNetwork } = useResourceContext();
  const networks = useNetworks();
  const [search, setSearch] = useState("");
  const items = networks.data?.pages.flatMap((page) => page.items) ?? [];
  useEffect(() => {
    if (
      search &&
      !items.some((item) =>
        item.display_name.toLowerCase().includes(search.toLowerCase()),
      ) &&
      networks.hasNextPage &&
      !networks.isFetching &&
      !networks.isError
    )
      void networks.fetchNextPage();
  }, [search, items, networks]);
  return (
    <section className="leader-concerns-page">
      <div className="leader-page-heading">
        <div>
          <span className="leader-kicker">BUSINESS FOCUS / 业务关注项</span>
          <Typography.Title level={1}>明确哪些流量最重要</Typography.Title>
          <p>
            按网络维护团队关注的关键流量。这里定义检查范围，不代表系统已经判断业务受影响。
          </p>
        </div>
        <div className="leader-network-picker">
          <label htmlFor="leader-network">所属网络</label>
          <Select
            id="leader-network"
            aria-label="所属网络"
            value={network?.id}
            placeholder="请选择网络"
            loading={networks.isFetching}
            showSearch={{ optionFilterProp: "label", onSearch: setSearch }}
            virtual={false}
            getPopupContainer={(trigger) => trigger.parentElement!}
            options={[
              ...items.map((item) => ({
                value: item.id,
                label: `${item.display_name} · ${item.id.slice(0, 8)}`,
                disabled: item.sync_state !== "ready",
              })),
              ...(network && !items.some((item) => item.id === network.id)
                ? [{ value: network.id, label: network.name }]
                : []),
            ]}
            onChange={(id) => {
              const item = items.find((candidate) => candidate.id === id);
              if (item)
                void selectNetwork({ id: item.id, name: item.display_name });
            }}
            popupRender={(menu) => (
              <>
                {menu}
                {networks.hasNextPage && (
                  <Button block onClick={() => void networks.fetchNextPage()}>
                    加载更多网络
                  </Button>
                )}
              </>
            )}
            notFoundContent={networks.isError ? "网络加载失败" : "暂无网络"}
          />
        </div>
      </div>
      {networks.isError && (
        <ErrorState
          error={networks.error}
          retry={() => void networks.refetch()}
        />
      )}
      {network ? (
        <ConcernCollection key={network.id} network={network} />
      ) : (
        <Card className="leader-concerns-empty">
          <Empty description="请选择一个网络，查看它的业务关注项" />
        </Card>
      )}
    </section>
  );
}

function ConcernCollection({
  network,
}: {
  network: { id: string; name: string };
}) {
  const session = useSession();
  const client = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [action, setAction] = useState<Concern | "create" | null>(null);
  const [detail, setDetail] = useState<Concern | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<Concern | null>(null);
  const [version, setVersion] = useState<number | null>(null);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm<ConcernDraft>();
  const watchedFlows = Form.useWatch("flows", form);
  useEffect(() => {
    if (action === "create") {
      form.setFieldsValue({
        name: "",
        description: null,
        priority: "medium",
        flows: [{ start_location: "", destination_ip: "" }],
      });
    } else if (action) {
      form.setFieldsValue({
        name: action.name,
        description: action.description,
        priority: action.priority,
        flows: action.flows,
      });
    }
  }, [action, form]);
  const key = resourceKey(
    session?.user_id ?? null,
    { networkId: network.id, snapshotId: null },
    "leader-business-concerns",
    { offset, limit: 20 },
  );
  const query = useQuery({
    queryKey: key,
    queryFn: ({ signal }) =>
      unwrap(
        api.GET("/api/v1/business-concerns", {
          signal,
          params: { query: { network_id: network.id, offset, limit: 20 } },
        }),
      ),
    enabled: !!session,
  });
  const history = useQuery({
    queryKey: resourceKey(
      session?.user_id ?? null,
      { networkId: network.id, snapshotId: null },
      "leader-business-concern-history",
      { id: detail?.id, version },
    ),
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/business-concerns/{concern_id}", {
          params: { path: { concern_id: detail!.id }, query: { version } },
        }),
      ),
    enabled: !!detail && version !== null,
  });
  const shown = version === null ? detail : history.data;

  function start(value: Concern | "create") {
    setError(undefined);
    form.resetFields();
    setAction(value);
  }
  async function save(values: ConcernDraft) {
    setError(undefined);
    try {
      const prepared = prepareConcern(network.id, values);
      setBusy(true);
      if (action === "create") {
        await unwrap(api.POST("/api/v1/business-concerns", { body: prepared }));
      } else if (action) {
        await unwrap(
          api.PATCH("/api/v1/business-concerns/{concern_id}", {
            params: { path: { concern_id: action.id } },
            body: {
              expected_version: action.version,
              name: prepared.name,
              description: prepared.description,
              priority: prepared.priority,
              flows: prepared.flows,
            },
          }),
        );
      }
      setAction(null);
      form.resetFields();
      await client.invalidateQueries({ queryKey: key });
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }
  async function archive(value: Concern) {
    setError(undefined);
    setBusy(true);
    try {
      await unwrap(
        api.PATCH("/api/v1/business-concerns/{concern_id}", {
          params: { path: { concern_id: value.id } },
          body: { expected_version: value.version, archived: true },
        }),
      );
      setDetail(null);
      await client.invalidateQueries({ queryKey: key });
      setArchiveTarget(null);
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }
  const isAdmin = session?.role === "admin";
  return (
    <>
      <div className="leader-concerns-toolbar">
        <div>
          <strong>{network.name}</strong>
          <span> · {query.data?.total ?? "—"} 个关注项</span>
        </div>
        {isAdmin && (
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => start("create")}
          >
            新增关注项
          </Button>
        )}
      </div>
      {error &&
        !action &&
        (error instanceof ApiError && error.code === "CONFLICT" ? (
          <Alert
            type="error"
            showIcon
            title="映射已被其他人修改，请刷新后检查。"
            action={
              <Button
                onClick={() => {
                  setError(undefined);
                  void query.refetch();
                }}
              >
                刷新
              </Button>
            }
          />
        ) : (
          <ErrorState error={error} />
        ))}
      {query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : query.isPending ? (
        <Card loading />
      ) : !query.data?.items.length ? (
        <Card className="leader-concerns-empty">
          <Empty description="这个网络还没有业务关注项" />
        </Card>
      ) : (
        <div className="leader-concern-grid">
          {query.data.items.map((item) => (
            <Card key={item.id} className="leader-concern-card">
              <div className="leader-concern-topline">
                <Tag
                  className="leader-priority-tag"
                  data-priority={item.priority}
                  color={priorityColors[item.priority]}
                >
                  {priorityLabels[item.priority]}重要度
                </Tag>
                <span>映射 v{item.version}</span>
              </div>
              <Typography.Title level={3}>{item.name}</Typography.Title>
              <p>{item.description || "尚未添加说明"}</p>
              <div className="leader-concern-bottom">
                <span>
                  <strong>{item.flows.length}</strong> 条关键流量
                </span>
                <Button
                  type="link"
                  onClick={() => {
                    setDetail(item);
                    setVersion(null);
                  }}
                >
                  查看范围 <ArrowRightOutlined />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      {(query.data?.total ?? 0) > 20 && (
        <Space className="leader-concern-pagination">
          <Button
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            上一页
          </Button>
          <span>第 {offset / 20 + 1} 页</span>
          <Button
            disabled={offset + 20 >= (query.data?.total ?? 0)}
            onClick={() => setOffset(offset + 20)}
          >
            下一页
          </Button>
        </Space>
      )}
      <Drawer
        title="关注项范围"
        size="large"
        open={!!detail}
        onClose={() => {
          setDetail(null);
          setVersion(null);
        }}
        extra={
          detail && (
            <Tag>映射 v{shown?.version ?? version ?? detail.version}</Tag>
          )
        }
      >
        {history.isError && (
          <ErrorState
            error={history.error}
            retry={() => void history.refetch()}
          />
        )}
        {shown && (
          <>
            <Descriptions
              column={1}
              items={[
                { key: "name", label: "名称", children: shown.name },
                {
                  key: "priority",
                  label: "重要程度",
                  children: priorityLabels[shown.priority],
                },
                { key: "network", label: "所属网络", children: network.name },
                {
                  key: "description",
                  label: "说明",
                  children: shown.description || "—",
                },
              ]}
            />
            <Typography.Title level={4}>关键流量范围</Typography.Title>
            {shown.flows.map((flow, index) => (
              <Card size="small" key={index} className="leader-flow-detail">
                <strong>
                  {flow.start_location} → {flow.destination_ip}
                </strong>
                <p>
                  {[
                    flow.source_ip && `源地址 ${flow.source_ip}`,
                    flow.protocol?.toUpperCase(),
                    flow.destination_port !== null &&
                      flow.destination_port !== undefined &&
                      `端口 ${flow.destination_port}`,
                  ]
                    .filter(Boolean)
                    .join(" · ") || "无附加条件"}
                </p>
              </Card>
            ))}
            <div className="leader-concern-history">
              <label htmlFor="concern-version">查看映射版本</label>
              <Select
                id="concern-version"
                aria-label="查看映射版本"
                value={version ?? detail?.version}
                loading={history.isFetching}
                options={Array.from(
                  { length: detail?.version ?? 0 },
                  (_, index) => ({ value: index + 1, label: `v${index + 1}` }),
                ).reverse()}
                onChange={(value) =>
                  setVersion(value === detail?.version ? null : value)
                }
              />
            </div>
            {isAdmin && version === null && !detail?.archived && (
              <Space>
                <Button
                  onClick={() => {
                    setDetail(null);
                    start(detail!);
                  }}
                >
                  编辑
                </Button>
                <Button
                  danger
                  disabled={busy}
                  onClick={() => setArchiveTarget(detail)}
                >
                  归档
                </Button>
              </Space>
            )}
          </>
        )}
      </Drawer>
      <Modal
        title={`归档“${archiveTarget?.name ?? ""}”？`}
        open={!!archiveTarget}
        onCancel={() => {
          if (!busy) setArchiveTarget(null);
        }}
        onOk={() => {
          if (archiveTarget) void archive(archiveTarget);
        }}
        okText="归档"
        okButtonProps={{ danger: true }}
        cancelText="取消"
        confirmLoading={busy}
      >
        {error !== undefined &&
          (error instanceof ApiError && error.code === "CONFLICT" ? (
            <Alert
              type="error"
              showIcon
              title="映射已被其他人修改，请取消并刷新后重试。"
            />
          ) : (
            <ErrorState error={error} />
          ))}
        归档后默认列表不再显示；已生成的汇报仍保留原版本事实。
      </Modal>
      <Modal
        title={action === "create" ? "新增关注项" : "编辑关注项"}
        open={!!action}
        width={700}
        onCancel={() => {
          if (!busy) {
            setAction(null);
            setError(undefined);
          }
        }}
        onOk={() => form.submit()}
        okText="保存映射"
        cancelText="取消"
        confirmLoading={busy}
        destroyOnHidden
      >
        {error !== undefined &&
          (error instanceof ApiError && error.code === "CONFLICT" ? (
            <Alert
              type="error"
              showIcon
              title="版本冲突：映射已被其他人修改。已保留您的填写内容；请取消后刷新，再检查新版本。"
            />
          ) : error instanceof Error && !(error instanceof ApiError) ? (
            <Alert type="error" showIcon title={error.message} />
          ) : (
            <ErrorState error={error} />
          ))}
        <Form<ConcernDraft>
          key={action === "create" ? "create" : action?.id}
          form={form}
          layout="vertical"
          initialValues={
            action === "create"
              ? {
                  priority: "medium",
                  flows: [{ start_location: "", destination_ip: "" }],
                }
              : (action ?? undefined)
          }
          onFinish={(values) => void save(values)}
          className="leader-concern-form"
        >
          <Form.Item
            label="名称"
            name="name"
            rules={[
              {
                required: true,
                whitespace: true,
                max: 128,
                message: "请输入不超过 128 字的名称",
              },
            ]}
          >
            <Input maxLength={128} placeholder="例如：订单系统访问" />
          </Form.Item>
          <Form.Item
            label="重要程度"
            name="priority"
            rules={[{ required: true }]}
          >
            <Select
              options={Object.entries(priorityLabels).map(([value, label]) => ({
                value,
                label,
              }))}
            />
          </Form.Item>
          <Form.Item
            label="说明（可选）"
            name="description"
            rules={[{ max: 2000 }]}
          >
            <Input.TextArea rows={2} maxLength={2000} />
          </Form.Item>
          <Typography.Title level={5}>关键流量</Typography.Title>
          <Form.List
            name="flows"
            rules={[
              {
                validator: async (_, flows) => {
                  if (!flows?.length) throw new Error("至少填写一条关键流量");
                },
              },
            ]}
          >
            {(fields, { add, remove }) => (
              <>
                {fields.map((field, index) => {
                  const advanced = watchedFlows?.[index];
                  const activeCount =
                    Number(!!advanced?.source_ip) +
                    Number(!!advanced?.protocol) +
                    Number(
                      advanced?.destination_port !== null &&
                        advanced?.destination_port !== undefined,
                    );
                  return (
                    <Card
                      key={field.key}
                      size="small"
                      className="leader-flow-form"
                      title={`流量 ${index + 1}`}
                      extra={
                        fields.length > 1 && (
                          <Button
                            type="link"
                            danger
                            onClick={() => remove(field.name)}
                          >
                            移除
                          </Button>
                        )
                      }
                    >
                      <Form.Item
                        label="起点"
                        name={[field.name, "start_location"]}
                        rules={[
                          {
                            required: true,
                            whitespace: true,
                            message: "请输入设备或位置",
                          },
                        ]}
                      >
                        <Input placeholder="例如：r1，或 Batfish 起点表达式" />
                      </Form.Item>
                      <Form.Item
                        label="目的 IPv4 地址"
                        name={[field.name, "destination_ip"]}
                        rules={[
                          { required: true, message: "请输入目的地址" },
                          {
                            pattern: /^(?:\d{1,3}\.){3}\d{1,3}$/,
                            message: "请输入 IPv4 地址",
                          },
                        ]}
                      >
                        <Input placeholder="例如：10.0.0.9" />
                      </Form.Item>
                      <AdvancedOptions activeCount={activeCount}>
                        <Form.Item
                          label="源 IPv4 地址（可选）"
                          name={[field.name, "source_ip"]}
                        >
                          <Input placeholder="例如：10.0.0.1" />
                        </Form.Item>
                        <Form.Item
                          label="协议（可选）"
                          name={[field.name, "protocol"]}
                        >
                          <Select
                            allowClear
                            options={protocols.map((value) => ({
                              value,
                              label: value.toUpperCase(),
                            }))}
                          />
                        </Form.Item>
                        <Form.Item
                          label="目的端口（仅 TCP / UDP）"
                          name={[field.name, "destination_port"]}
                        >
                          <InputNumber
                            min={0}
                            max={65535}
                            style={{ width: "100%" }}
                          />
                        </Form.Item>
                      </AdvancedOptions>
                    </Card>
                  );
                })}
                <Button
                  disabled={fields.length >= 10}
                  onClick={() =>
                    add({ start_location: "", destination_ip: "" })
                  }
                >
                  添加流量
                </Button>
              </>
            )}
          </Form.List>
          <div className="leader-scope-preview">
            <strong>提交范围 · {network.name}</strong>
            <span>
              {watchedFlows?.length ?? 0}{" "}
              条关键流量；未填写的高级条件不参与范围。
            </span>
            {(watchedFlows ?? []).map((flow, index) => (
              <small key={index}>
                {index + 1}. {flow?.start_location || "起点待填"} →{" "}
                {flow?.destination_ip || "目的地址待填"}
                {flow?.protocol ? ` · ${flow.protocol.toUpperCase()}` : ""}
                {flow?.destination_port !== undefined &&
                flow?.destination_port !== null
                  ? ` :${flow.destination_port}`
                  : ""}
                {flow?.source_ip ? ` · 源 ${flow.source_ip}` : ""}
              </small>
            ))}
          </div>
        </Form>
      </Modal>
      <p className="leader-footnote">
        关注项是人工维护的检查范围，不是检查结论。需要网络配置和快照管理时，可前往{" "}
        <Link to="/networks">技术工作台</Link>。
      </p>
    </>
  );
}
