import {
  useEffect,
  useState,
  Suspense,
  lazy,
  type PropsWithChildren,
} from "react";
import {
  Layout,
  Menu,
  Typography,
  Card,
  Space,
  Tag,
  Steps,
  Button,
} from "antd";
import { ThemeProvider, ThemeControl } from "./theme";
import { ServiceStatus } from "./ServiceStatus";
import { chooseEntry, preferredEntryPath } from "./entry";
import {
  ApartmentOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  BranchesOutlined,
  ClockCircleOutlined,
  QuestionCircleOutlined,
} from "@ant-design/icons";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createBrowserRouter,
  RouterProvider,
  Routes,
  Route,
  Link,
  useLocation,
  Navigate,
} from "react-router-dom";
import { ContextProvider, useResourceContext } from "./context";
import { onIdentityChange, useSession } from "./session";
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
import { LeaderShell } from "../features/leader/LeaderShell";
import { ConcernsPage } from "../features/leader/concerns/ConcernsPage";
import { LeaderChecksPage } from "../features/leader/checks/ChecksPage";
import {
  LeaderOverviewPage,
  LeaderNetworkPage,
} from "../features/leader/overview/OverviewPage";
const TracePage = lazy(() =>
  import("../features/traceroute/TraceForm").then((m) => ({
    default: m.TracePage,
  })),
);
const TopologyPage = lazy(() =>
  import("../features/topology/TopologyPage").then((m) => ({
    default: m.TopologyPage,
  })),
);
const BgpPage = lazy(() =>
  import("../features/bgp/BgpPage").then((m) => ({ default: m.BgpPage })),
);
const FilterTestPage = lazy(() =>
  import("../features/acl/FilterTest").then((m) => ({
    default: m.FilterTestPage,
  })),
);
const ExpertPage = lazy(() =>
  import("../features/expert/ExpertForm").then((m) => ({
    default: m.ExpertPage,
  })),
);
const ChangesPage = lazy(() =>
  import("../features/changes/ChangesPage").then((m) => ({
    default: m.ChangesPage,
  })),
);
const FaultsPage = lazy(() =>
  import("../features/faults/FaultsPage").then((m) => ({
    default: m.FaultsPage,
  })),
);
const AnalysisPage = lazy(() =>
  import("../features/inventory/Analysis").then((m) => ({
    default: m.AnalysisPage,
  })),
);
const ResultsPage = lazy(() =>
  import("../features/results/Results").then((m) => ({
    default: m.ResultsPage,
  })),
);
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
const JobsPage = lazy(() =>
  import("../features/jobs/Jobs").then((m) => ({ default: m.JobsPage })),
);
const JobDetail = lazy(() =>
  import("../features/jobs/Jobs").then((m) => ({ default: m.JobDetail })),
);
const DiagnosticsPage = lazy(() =>
  import("../features/snapshots/diagnostics/Diagnostics").then((m) => ({
    default: m.DiagnosticsPage,
  })),
);
const UsersPage = lazy(() =>
  import("../features/users/Users").then((module) => ({
    default: module.UsersPage,
  })),
);
import "./style.css";
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
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <ContextProvider key={session?.user_id ?? "anonymous"}>
          {children}
        </ContextProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
export function Shell({ children }: PropsWithChildren) {
  const location = useLocation();
  const session = useSession();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
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
          selectedKeys={[
            location.pathname.startsWith("/analysis") ||
            location.pathname === "/traceroute" ||
            location.pathname.startsWith("/results/")
              ? "/analysis"
              : location.pathname.startsWith("/jobs/")
                ? "/jobs"
                : location.pathname === "/snapshots" ||
                    location.pathname.includes("/diagnostics")
                  ? "/networks"
                  : location.pathname,
          ]}
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
              label: <Link to="/analysis/nodes">网络分析</Link>,
            },
            {
              key: "/topology",
              icon: <ApartmentOutlined />,
              label: <Link to="/topology">网络拓扑</Link>,
            },
            {
              key: "/bgp",
              icon: <BranchesOutlined />,
              label: <Link to="/bgp">BGP 会话</Link>,
            },
            {
              key: "/acl",
              icon: <BranchesOutlined />,
              label: <Link to="/acl">ACL 流量测试</Link>,
            },
            {
              key: "/expert",
              icon: <QuestionCircleOutlined />,
              label: <Link to="/expert">专家查询</Link>,
            },
            {
              key: "/changes",
              icon: <BranchesOutlined />,
              label: <Link to="/changes">变更对比</Link>,
            },
            {
              key: "/faults",
              icon: <BranchesOutlined />,
              label: <Link to="/faults">故障模拟</Link>,
            },
            {
              key: "/jobs",
              icon: <ClockCircleOutlined />,
              label: <Link to="/jobs">任务中心</Link>,
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
          <Space className="account-controls">
            <ThemeControl />
            <ServiceStatus />
            <Link
              to="/leader/overview"
              className="account-link"
              onClick={() => chooseEntry("leader")}
            >
              领导视图
            </Link>
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
  const location = useLocation();
  const leaderRoute = location.pathname.startsWith("/leader");
  return (
    <Providers>
      <SessionBootstrap>
        <AuthGuard>
          {leaderRoute ? (
            <LeaderShell>
              <Routes>
                <Route
                  path="/leader/overview"
                  element={<LeaderOverviewPage />}
                />
                <Route
                  path="/leader/networks/:networkId"
                  element={<LeaderNetworkPage />}
                />
                <Route path="/leader/concerns" element={<ConcernsPage />} />
                <Route path="/leader/checks" element={<LeaderChecksPage />} />
                <Route
                  path="/leader/checks/:runId"
                  element={<LeaderChecksPage />}
                />
                <Route
                  path="/leader"
                  element={<Navigate to="/leader/overview" replace />}
                />
                <Route
                  path="*"
                  element={<Navigate to="/leader/overview" replace />}
                />
              </Routes>
            </LeaderShell>
          ) : (
            <Shell>
              <Suspense fallback={<LoadingState />}>
                <Routes>
                  <Route path="/topology" element={<TopologyPage />} />
                  <Route path="/bgp" element={<BgpPage />} />
                  <Route path="/acl" element={<FilterTestPage />} />
                  <Route path="/expert" element={<ExpertPage />} />
                  <Route path="/changes" element={<ChangesPage />} />
                  <Route path="/faults" element={<FaultsPage />} />
                  <Route path="/traceroute" element={<TracePage />} />
                  <Route
                    path="/analysis/:operation"
                    element={<AnalysisPage />}
                  />
                  <Route path="/analysis" element={<AnalysisPage />} />
                  <Route path="/results/:resultId" element={<ResultsPage />} />
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
                  <Route path="/jobs" element={<JobsPage />} />
                  <Route
                    path="/networks/:networkId/snapshots/:snapshotId/diagnostics"
                    element={<DiagnosticsPage />}
                  />
                  <Route path="/jobs/:jobId" element={<JobDetail />} />
                  <Route path="/password" element={<PasswordPage />} />
                  <Route
                    path="/"
                    element={
                      preferredEntryPath() === "/leader/overview" ? (
                        <Navigate to="/leader/overview" replace />
                      ) : (
                        <Overview />
                      )
                    }
                  />
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
          )}
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
