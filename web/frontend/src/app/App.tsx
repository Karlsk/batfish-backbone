import {
  useEffect,
  useState,
  Suspense,
  lazy,
  type PropsWithChildren,
} from "react";
import {
  ConfigProvider,
  Layout,
  Menu,
  Typography,
  Card,
  Space,
  Tag,
  Badge,
  Select,
  Steps,
  Button,
} from "antd";
import zhCN from "antd/locale/zh_CN";
import {
  ApartmentOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  BranchesOutlined,
  ClockCircleOutlined,
  QuestionCircleOutlined,
} from "@ant-design/icons";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import {
  createBrowserRouter,
  RouterProvider,
  Routes,
  Route,
  Link,
  useLocation,
} from "react-router-dom";
import { ContextProvider, useResourceContext, resourceKey } from "./context";
import { onIdentityChange, useSession } from "./session";
import { api, unwrap } from "../api/client";
import { EmptyState } from "../components/States";
import {
  SessionBootstrap,
  AuthGuard,
  LogoutButton,
  PasswordPage,
} from "../features/auth/Auth";
import { AdminOnly } from "../features/users/Access";
import { ContextPicker } from "../features/networks/ContextPicker";
import { LoadingState } from "../components/States";
const NetworksPage = lazy(() =>
  import("../features/networks/Networks").then((m) => ({
    default: m.NetworksPage,
  })),
);
const SnapshotsPage = lazy(() =>
  import("../features/snapshots/Snapshots").then((m) => ({
    default: m.SnapshotsPage,
  })),
);
const InitializationJobPage = lazy(() =>
  import("../features/snapshots/Snapshots").then((m) => ({
    default: m.InitializationJobPage,
  })),
);
const UsersPage = lazy(() =>
  import("../features/users/Users").then((module) => ({
    default: module.UsersPage,
  })),
);
import "./style.css";
export const theme = {
  token: {
    colorPrimary: "#2563eb",
    colorBgLayout: "#f4f6fa",
    colorText: "#202c40",
    colorTextSecondary: "#66758b",
    borderRadius: 8,
    fontSize: 14,
    fontFamily:
      'Inter, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif',
  },
  components: {
    Layout: { headerBg: "#ffffff", siderBg: "#ffffff" },
    Menu: { itemBorderRadius: 8, itemHeight: 44 },
  },
};
export function Providers({ children }: PropsWithChildren) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, staleTime: 15000, refetchOnWindowFocus: false },
        },
      }),
  );
  useEffect(() => onIdentityChange(() => client.clear()), [client]);
  const session = useSession();
  return (
    <ConfigProvider
      locale={zhCN}
      theme={theme}
      button={{ autoInsertSpace: false }}
    >
      <QueryClientProvider client={client}>
        <ContextProvider key={session?.user_id ?? "anonymous"}>
          {children}
        </ContextProvider>
      </QueryClientProvider>
    </ConfigProvider>
  );
}
function ServiceStatus() {
  const health = useQuery({
    queryKey: resourceKey(
      null,
      { networkId: null, snapshotId: null },
      "health",
    ),
    queryFn: () => unwrap(api.GET("/api/v1/health/ready")),
    refetchInterval: 30000,
  });
  return (
    <Badge
      status={
        health.isSuccess
          ? "success"
          : health.isPending
            ? "processing"
            : "warning"
      }
      text={
        health.isSuccess
          ? "服务就绪"
          : health.isPending
            ? "正在连接"
            : "服务未就绪"
      }
    />
  );
}
export function Shell({ children }: PropsWithChildren) {
  const { network, snapshot } = useResourceContext();
  const location = useLocation();
  const session = useSession();
  return (
    <Layout className="workbench">
      <Layout.Sider width={224} className="sidebar">
        <Link to="/" className="brand">
          <span className="brand-mark">
            <ApartmentOutlined />
          </span>
          <span>
            Batfish<small>网络分析工作台</small>
          </span>
        </Link>
        <div className="nav-caption">工作空间</div>
        <Menu
          selectedKeys={[location.pathname]}
          items={[
            ...(session?.role === "admin"
              ? [
                  {
                    key: "/users",
                    icon: <ApartmentOutlined />,
                    label: <Link to="/users">用户管理</Link>,
                  },
                ]
              : []),
            {
              key: "/",
              icon: <DashboardOutlined />,
              label: <Link to="/">概览</Link>,
            },
            {
              key: "/networks",
              icon: <DatabaseOutlined />,
              label: <Link to="/networks">网络与快照</Link>,
            },
            {
              key: "/analysis",
              icon: <BranchesOutlined />,
              label: "网络分析",
              disabled: true,
            },
            {
              key: "/jobs",
              icon: <ClockCircleOutlined />,
              label: "任务中心",
              disabled: true,
            },
          ]}
        />
        <div className="sidebar-footer">
          <QuestionCircleOutlined /> 基于配置的模型分析
          <br />
          <small>从结论到证据，逐级查看</small>
        </div>
      </Layout.Sider>
      <Layout className="main-layout">
        <Layout.Header className="topbar">
          <ContextPicker />
          <Space>
            <ServiceStatus />
            {session && (
              <>
                <Link
                  to="/password"
                  className="account-link"
                  title={`${session.username} · 改密`}
                >
                  {session.username} · 改密
                </Link>
                <LogoutButton />
              </>
            )}
          </Space>
        </Layout.Header>
        <Layout.Content className="page-content">{children}</Layout.Content>
      </Layout>
    </Layout>
  );
}
function Overview() {
  const { network, snapshot } = useResourceContext();
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">WORKSPACE OVERVIEW</div>
          <Typography.Title level={2}>
            网络分析，从一份配置开始
          </Typography.Title>
          <Typography.Paragraph type="secondary">
            组织网络与快照，在同一工作空间查看设备、路由和路径推演。
          </Typography.Paragraph>
        </div>
        <Tag color="blue">基础工作台</Tag>
      </div>
      <Card
        className="getting-started"
        title="开始使用"
        extra={
          <Typography.Text type="secondary">清晰的三步流程</Typography.Text>
        }
      >
        <Steps
          items={[
            { title: "选择网络", content: "按环境组织配置" },
            { title: "初始化快照", content: "先查看解析质量" },
            { title: "执行分析", content: "从摘要深入证据" },
          ]}
        />
      </Card>
      <div className="overview-grid">
        <Card title="当前上下文">
          <EmptyState
            title={network ? network.name : "尚未选择网络与快照"}
            description={
              snapshot
                ? `当前快照：${snapshot.name}`
                : "选择网络后上传配置，开始分析。"
            }
            action={
              <Link to={network ? "/snapshots" : "/networks"}>
                <Button type="primary">
                  {network ? "查看快照" : "选择或创建网络"}
                </Button>
              </Link>
            }
          />
        </Card>
        <Card title="分析使用原则">
          <Space orientation="vertical" size={22}>
            <div>
              <strong>最少输入，按需展开</strong>
              <p>默认展示必要参数，高级选项保留已填写内容。</p>
            </div>
            <div>
              <strong>先看结论，再看详情</strong>
              <p>摘要呈现主要信息，原始证据在详情中查看。</p>
            </div>
            <div>
              <strong>始终保留模型边界</strong>
              <p>解析警告、覆盖限制和截断信息伴随结果展示。</p>
            </div>
          </Space>
        </Card>
      </div>
      <div className="page-footnote">
        模型推演基于快照配置，不代表在线探测或实际设备状态。
      </div>
    </>
  );
}
function WorkbenchRoutes() {
  return (
    <Providers>
      <SessionBootstrap>
        <AuthGuard>
          <Shell>
            <Suspense fallback={<LoadingState />}>
              <Routes>
                <Route
                  path="/users"
                  element={
                    <AdminOnly>
                      <UsersPage />
                    </AdminOnly>
                  }
                />
                <Route path="/networks" element={<NetworksPage />} />
                <Route path="/snapshots" element={<SnapshotsPage />} />
                <Route
                  path="/jobs/:jobId"
                  element={<InitializationJobPage />}
                />
                <Route path="/password" element={<PasswordPage />} />
                <Route path="/" element={<Overview />} />
                <Route
                  path="*"
                  element={
                    <EmptyState
                      title="页面暂未开放"
                      action={
                        <Link to="/">
                          <Button>返回概览</Button>
                        </Link>
                      }
                    />
                  }
                />
              </Routes>
            </Suspense>
          </Shell>
        </AuthGuard>
      </SessionBootstrap>
    </Providers>
  );
}

export function App() {
  const [router] = useState(() =>
    createBrowserRouter([{ path: "*", element: <WorkbenchRoutes /> }]),
  );
  return <RouterProvider router={router} />;
}
