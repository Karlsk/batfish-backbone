import { useEffect, useState, type PropsWithChildren } from "react";
import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, unwrap, ApiError } from "../../api/client";
import {
  getSession,
  setSession,
  useSession,
  sessionGeneration,
} from "../../app/session";
import { ErrorState, LoadingState } from "../../components/States";
export async function refreshSession() {
  const generation = sessionGeneration();
  try {
    const session = await unwrap(api.GET("/api/v1/auth/me"));
    if (generation === sessionGeneration()) setSession(session);
  } catch (error) {
    if (error instanceof ApiError && error.code === "UNAUTHORIZED") return;
    throw error;
  }
}
export function SessionBootstrap({ children }: PropsWithChildren) {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    let active = true;
    void refreshSession()
      .then(() => {
        if (active) {
          setReady(true);
          setError(undefined);
        }
      })
      .catch((e) => {
        if (active) setError(e);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    const refresh = () => {
      if (getSession()) void refreshSession().catch(() => {});
    };
    window.addEventListener("focus", refresh);
    const timer = window.setInterval(refresh, 30000);
    return () => {
      window.removeEventListener("focus", refresh);
      window.clearInterval(timer);
    };
  }, []);
  if (error)
    return (
      <div className="auth-screen">
        <ErrorState error={error} retry={() => window.location.reload()} />
      </div>
    );
  return ready ? children : <LoadingState />;
}
export function AuthGuard({ children }: PropsWithChildren) {
  const session = useSession();
  if (!session) return <LoginPage />;
  if (session.must_change_password) return <PasswordPage forced />;
  return children;
}
export function LoginPage() {
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  return (
    <div className="auth-screen">
      <Card className="auth-card">
        <div className="eyebrow">BATFISH WORKSPACE</div>
        <Typography.Title level={2}>登录工作台</Typography.Title>
        <p className="auth-intro">使用团队账号访问网络、快照与分析结果。</p>
        {params.get("password_changed") === "1" && (
          <Alert
            type="success"
            title="密码已更新，请使用新密码登录。"
            showIcon
          />
        )}
        {!!error && (
          <ErrorState
            error={
              error instanceof ApiError && error.code === "UNAUTHORIZED"
                ? new ApiError("LOGIN_FAILED")
                : error
            }
          />
        )}
        <Form
          form={form}
          layout="vertical"
          onFinish={async (values) => {
            setBusy(true);
            setError(undefined);
            try {
              const session = await unwrap(
                api.POST("/api/v1/auth/login", { body: values }),
              );
              form.resetFields();
              setSession(session);
              navigate("/", { replace: true });
            } catch (e) {
              setError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input autoComplete="username" maxLength={128} />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password autoComplete="current-password" maxLength={128} />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={busy}>
            登录
          </Button>
        </Form>
        <p className="auth-note">账号由管理员创建；多次失败将触发短暂限流。</p>
      </Card>
    </div>
  );
}
export function PasswordPage({ forced = false }: { forced?: boolean }) {
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const content = (
    <Card className="auth-card">
      <Typography.Title level={2}>
        {forced ? "设置新密码" : "修改密码"}
      </Typography.Title>
      <p className="auth-intro">
        {forced
          ? "首次登录或密码重置后，需先修改临时密码。"
          : "修改密码后，所有已有会话将失效。"}
      </p>
      {!!error && <ErrorState error={error} />}
      <Form
        form={form}
        layout="vertical"
        onFinish={async (values) => {
          setBusy(true);
          setError(undefined);
          try {
            await unwrap(
              api.POST("/api/v1/auth/password", {
                body: {
                  current_password: values.current_password,
                  new_password: values.new_password,
                },
              }),
            );
            form.resetFields();
            setSession(null);
            navigate("/?password_changed=1", { replace: true });
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        <Form.Item
          name="current_password"
          label="当前密码"
          rules={[{ required: true, message: "请输入当前密码" }]}
        >
          <Input.Password autoComplete="current-password" maxLength={128} />
        </Form.Item>
        <Form.Item
          name="new_password"
          label="新密码"
          rules={[
            { required: true, message: "请输入新密码" },
            { min: 12, message: "至少12个字符" },
          ]}
        >
          <Input.Password autoComplete="new-password" maxLength={128} />
        </Form.Item>
        <Form.Item
          name="confirm_password"
          label="确认新密码"
          dependencies={["new_password"]}
          rules={[
            { required: true, message: "请再次输入新密码" },
            ({ getFieldValue }) => ({
              validator: (_, value) =>
                value === getFieldValue("new_password")
                  ? Promise.resolve()
                  : Promise.reject(new Error("两次密码不一致")),
            }),
          ]}
        >
          <Input.Password autoComplete="new-password" maxLength={128} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={busy} block>
          更新密码并重新登录
        </Button>
      </Form>
      {forced ? <LogoutButton /> : <Link to="/">返回概览</Link>}
    </Card>
  );
  return forced ? <div className="auth-screen">{content}</div> : content;
}
export function LogoutButton() {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  return (
    <>
      {!!error && <ErrorState error={error} />}
      <Button
        type="text"
        loading={busy}
        onClick={async () => {
          setBusy(true);
          setError(undefined);
          try {
            await unwrap(api.POST("/api/v1/auth/logout"));
            setSession(null);
            client.clear();
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        退出登录
      </Button>
    </>
  );
}
