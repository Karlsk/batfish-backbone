import { useState } from "react";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, ApiError } from "../../api/client";
import type { components } from "../../api/schema";
import { useSession } from "../../app/session";
import { resourceKey } from "../../app/context";
import { ErrorState } from "../../components/States";
import { refreshSession } from "../auth/Auth";
type User = components["schemas"]["UserDTO"];
export function UserMutationError({
  error,
  operation,
}: {
  error: unknown;
  operation?: string;
}) {
  if (error instanceof ApiError && error.code === "CONFLICT")
    return (
      <Alert
        type="error"
        showIcon
        title={
          operation === "create"
            ? "用户名已存在，请换一个名称。"
            : "操作冲突：系统必须保留至少一位启用的管理员，请刷新后检查。"
        }
      />
    );
  return <ErrorState error={error} />;
}
export function UsersPage() {
  const session = useSession();
  const client = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [detail, setDetail] = useState<User | null>(null);
  const [action, setAction] = useState<{
    kind: "create" | "reset" | "edit";
    user?: User;
  } | null>(null);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const key = resourceKey(
    session?.user_id ?? null,
    { networkId: null, snapshotId: null },
    "users",
    { offset, limit: 20 },
  );
  const query = useQuery({
    queryKey: key,
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/users", { params: { query: { offset, limit: 20 } } }),
      ),
    enabled: session?.role === "admin",
    retry: false,
  });
  function start(kind: "create" | "reset" | "edit", user?: User) {
    setError(undefined);
    form.resetFields();
    setAction({ kind, user });
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <Typography.Title level={2}>用户管理</Typography.Title>
          <Typography.Paragraph type="secondary">
            管理团队访问权限；所有成员共享网络与分析资源。
          </Typography.Paragraph>
        </div>
        <Button type="primary" onClick={() => start("create")}>
          创建用户
        </Button>
      </div>
      {query.isError ? (
        <ErrorState error={query.error} retry={() => void query.refetch()} />
      ) : (
        <Card>
          <Table<User>
            rowKey="id"
            loading={query.isPending}
            dataSource={query.data?.items}
            pagination={{
              current: offset / 20 + 1,
              pageSize: 20,
              total: query.data?.total,
              showSizeChanger: false,
              onChange: (page) => setOffset((page - 1) * 20),
            }}
            columns={[
              { title: "用户名", dataIndex: "username", ellipsis: true },
              {
                title: "角色",
                dataIndex: "role",
                render: (value) => (value === "admin" ? "管理员" : "普通成员"),
              },
              {
                title: "状态",
                render: (_, user) => (
                  <Space>
                    <Tag color={user.enabled ? "green" : "default"}>
                      {user.enabled ? "已启用" : "已停用"}
                    </Tag>
                    {user.must_change_password && <Tag>待改密</Tag>}
                  </Space>
                ),
              },
              {
                title: "操作",
                render: (_, user) => (
                  <Space>
                    <Button type="link" onClick={() => setDetail(user)}>
                      详情
                    </Button>
                    <Button type="link" onClick={() => start("edit", user)}>
                      编辑权限
                    </Button>
                    <Button type="link" onClick={() => start("reset", user)}>
                      重置密码
                    </Button>
                  </Space>
                ),
              },
            ]}
          />
        </Card>
      )}
      <Drawer open={!!detail} title="用户详情" onClose={() => setDetail(null)}>
        {detail && (
          <Descriptions
            column={1}
            items={[
              { key: "name", label: "用户名", children: detail.username },
              {
                key: "role",
                label: "角色",
                children: detail.role === "admin" ? "管理员" : "普通成员",
              },
              {
                key: "created",
                label: "创建时间",
                children: new Date(detail.created_at).toLocaleString("zh-CN"),
              },
              { key: "id", label: "用户编号", children: detail.id },
            ]}
          />
        )}
      </Drawer>
      <Modal
        open={!!action}
        title={
          action?.kind === "create"
            ? "创建用户"
            : action?.kind === "reset"
              ? `重置密码 · ${action.user?.username}`
              : `编辑权限 · ${action?.user?.username}`
        }
        onCancel={() => {
          if (!busy) {
            setAction(null);
            form.resetFields();
            setError(undefined);
          }
        }}
        onOk={() => form.submit()}
        confirmLoading={busy}
        cancelButtonProps={{ disabled: busy }}
        destroyOnHidden
        okText="保存"
        cancelText="取消"
      >
        {!!error && (
          <UserMutationError error={error} operation={action?.kind} />
        )}
        <Form
          key={`${action?.kind}-${action?.user?.id ?? "new"}`}
          initialValues={
            action?.kind === "create"
              ? { role: "member" }
              : {
                  role: action?.user?.role,
                  enabled: action?.user?.enabled ? "enabled" : "disabled",
                }
          }
          form={form}
          layout="vertical"
          preserve={false}
          onFinish={async (values) => {
            if (!action) return;
            setBusy(true);
            setError(undefined);
            try {
              if (action.kind === "create")
                await unwrap(
                  api.POST("/api/v1/users", {
                    body: {
                      username: values.username,
                      temporary_password: values.temporary_password,
                      role: values.role,
                    },
                  }),
                );
              else if (action.kind === "reset")
                await unwrap(
                  api.POST("/api/v1/users/{user_id}/reset-password", {
                    params: { path: { user_id: action.user!.id } },
                    body: { temporary_password: values.temporary_password },
                  }),
                );
              else
                await unwrap(
                  api.PATCH("/api/v1/users/{user_id}", {
                    params: { path: { user_id: action.user!.id } },
                    body: {
                      enabled: values.enabled === "enabled",
                      role: values.role,
                    },
                  }),
                );
              form.resetFields();
              setAction(null);
              await client.invalidateQueries({
                predicate: (q) => q.queryKey[5] === "users",
              });
              if (action.user?.id === session?.user_id) await refreshSession();
            } catch (e) {
              setError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          {action?.kind === "create" && (
            <Form.Item
              name="username"
              label="用户名"
              rules={[{ required: true, message: "请输入用户名" }]}
            >
              <Input autoComplete="off" maxLength={128} />
            </Form.Item>
          )}
          {action?.kind !== "reset" && (
            <Form.Item name="role" label="角色" rules={[{ required: true }]}>
              <Select
                virtual={false}
                options={[
                  { value: "member", label: "普通成员" },
                  { value: "admin", label: "管理员" },
                ]}
              />
            </Form.Item>
          )}
          {action?.kind === "edit" ? (
            <Form.Item
              name="enabled"
              label="账号状态"
              rules={[{ required: true }]}
            >
              <Select
                virtual={false}
                options={[
                  { value: "enabled", label: "启用" },
                  { value: "disabled", label: "停用" },
                ]}
              />
            </Form.Item>
          ) : (
            <>
              <Form.Item
                name="temporary_password"
                label="临时密码"
                rules={[
                  { required: true, message: "请输入临时密码" },
                  { min: 12, message: "至少12个字符" },
                ]}
              >
                <Input.Password autoComplete="new-password" maxLength={128} />
              </Form.Item>
              <Alert
                type="info"
                showIcon
                title="用户下次登录必须改密；此密码不会被页面持久保存。"
              />
            </>
          )}
        </Form>
      </Modal>
    </>
  );
}
