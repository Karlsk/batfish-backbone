import { useRef, useState, useEffect } from "react";
import { Button, Card, Form, Input, Modal, Table, Tag, Typography } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api, unwrap } from "../../api/client";
import { useResourceContext } from "../../app/context";
import { ErrorState } from "../../components/States";
import { useNetworks } from "./queries";
import type { components } from "../../api/schema";
export function NetworksPage() {
  const query = useNetworks();
  const client = useQueryClient();
  const { selectNetwork } = useResourceContext();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [frozen, setFrozen] = useState(false);
  const [form] = Form.useForm();
  const key = useRef("");
  const inFlight = useRef(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  return (
    <>
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>网络与快照</Typography.Title>
          <Typography.Paragraph type="secondary">
            先选择网络，再上传配置并初始化快照。相同名称通过编号区分。
          </Typography.Paragraph>
        </div>
        <Button
          type="primary"
          onClick={() => {
            key.current = crypto.randomUUID();
            form.resetFields();
            setFrozen(false);
            setError(undefined);
            setOpen(true);
          }}
        >
          创建网络
        </Button>
      </div>
      {query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : (
        <Card>
          <Table<components["schemas"]["NetworkDTO"]>
            rowKey="id"
            dataSource={query.data?.pages.flatMap((page) => page.items)}
            loading={query.isPending}
            pagination={false}
            locale={{ emptyText: "暂无网络，点击“创建网络”开始。" }}
            columns={[
              {
                title: "网络名称",
                render: (_, n) => (
                  <>
                    <strong>{n.display_name}</strong>
                    <div className="record-id">{n.id}</div>
                  </>
                ),
              },
              {
                title: "状态",
                render: (_, n) => (
                  <Tag color={n.sync_state === "ready" ? "green" : "orange"}>
                    {
                      {
                        pending: "准备中",
                        ready: "可用",
                        failed: "失败",
                        deleting: "删除中",
                        deleted: "已删除",
                      }[n.sync_state]
                    }
                  </Tag>
                ),
              },
              {
                title: "发起人",
                dataIndex: "created_by",
                render: (value) => (
                  <span title={value}>{value.slice(0, 8)}</span>
                ),
              },
              {
                title: "创建时间",
                dataIndex: "created_at",
                render: (value) => new Date(value).toLocaleString("zh-CN"),
              },
              {
                title: "操作",
                render: (_, n) => (
                  <Button
                    disabled={n.sync_state !== "ready"}
                    type="link"
                    onClick={async () => {
                      if (
                        await selectNetwork({ id: n.id, name: n.display_name })
                      )
                        navigate("/snapshots");
                    }}
                  >
                    查看快照
                  </Button>
                ),
              },
            ]}
          />
          {query.hasNextPage && (
            <Button
              onClick={() => void query.fetchNextPage()}
              loading={query.isFetchingNextPage}
            >
              加载更多网络
            </Button>
          )}
        </Card>
      )}
      <Modal
        title="创建网络"
        open={open}
        onCancel={() => {
          if (!busy) setOpen(false);
        }}
        onOk={() => form.submit()}
        confirmLoading={busy}
        okText={frozen ? "重试创建" : "创建"}
        cancelText="取消"
        destroyOnHidden
      >
        <p>网络仅用于组织配置。同名网络仍为独立资源。</p>
        {!!error && <ErrorState error={error} />}
        <Form
          form={form}
          layout="vertical"
          onFinish={async (values) => {
            if (inFlight.current) return;
            inFlight.current = true;
            setBusy(true);
            setFrozen(true);
            setError(undefined);
            try {
              const network = await unwrap(
                api.POST("/api/v1/networks", {
                  body: { display_name: values.display_name },
                  params: { header: { "idempotency-key": key.current } },
                }),
              );
              await client.invalidateQueries({
                predicate: (q) => q.queryKey[5] === "networks",
              });
              if (alive.current) {
                setOpen(false);
                await selectNetwork({
                  id: network.id,
                  name: network.display_name,
                });
                navigate("/snapshots");
              }
            } catch (e) {
              if (alive.current) setError(e);
            } finally {
              inFlight.current = false;
              if (alive.current) setBusy(false);
            }
          }}
        >
          <Form.Item
            name="display_name"
            label="网络名称"
            rules={[
              { required: true, whitespace: true, message: "请输入网络名称" },
            ]}
          >
            <Input maxLength={255} disabled={frozen} />
          </Form.Item>
        </Form>
        {frozen && (
          <p className="muted">
            重试保留原参数与请求编号。若离开，请先检查网络列表是否已创建。
          </p>
        )}
      </Modal>
    </>
  );
}
