import { useEffect, type PropsWithChildren } from "react";
import { Layout, Space } from "antd";
import { ArrowRightOutlined, RadarChartOutlined } from "@ant-design/icons";
import { Link, useLocation } from "react-router-dom";
import { ThemeControl } from "../../app/theme";
import { ServiceStatus } from "../../app/ServiceStatus";
import { chooseEntry } from "../../app/entry";
import { useSession } from "../../app/session";
import { LogoutButton } from "../auth/Auth";

export function LeaderShell({ children }: PropsWithChildren) {
  const location = useLocation();
  const session = useSession();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
  return (
    <Layout className="leader-workbench">
      <header className="leader-topbar">
        <Link className="leader-brand" to="/leader/overview">
          <span className="leader-brand-mark" aria-hidden="true">
            <RadarChartOutlined />
          </span>
          <span>
            BATFISH <small>网络洞察</small>
          </span>
        </Link>
        <nav className="leader-navigation" aria-label="领导视图导航">
          <Link
            to="/leader/overview"
            aria-current={
              location.pathname === "/leader/overview" ? "page" : undefined
            }
          >
            总览
          </Link>
          <Link
            to="/leader/concerns"
            aria-current={
              location.pathname === "/leader/concerns" ? "page" : undefined
            }
          >
            业务关注项
          </Link>
          <Link
            to="/leader/checks"
            aria-current={
              location.pathname.startsWith("/leader/checks")
                ? "page"
                : undefined
            }
          >
            自主检查
          </Link>
          <Link
            to="/leader/changes"
            aria-current={
              location.pathname.startsWith("/leader/changes") ||
              location.pathname.startsWith("/leader/faults")
                ? "page"
                : undefined
            }
          >
            变更与故障
          </Link>
          <Link
            to="/leader/briefings"
            aria-current={
              location.pathname.startsWith("/leader/briefings")
                ? "page"
                : undefined
            }
          >
            固定汇报
          </Link>
        </nav>
        <Space className="leader-controls" wrap>
          <ThemeControl />
          <ServiceStatus />
          {session && (
            <Link to="/password" className="account-link">
              {session.username} · 改密
            </Link>
          )}
          <Link
            to="/"
            className="leader-mode-switch"
            onClick={() => chooseEntry("technical")}
          >
            技术工作台 <ArrowRightOutlined />
          </Link>
          <LogoutButton />
        </Space>
      </header>
      <main className="leader-main">{children}</main>
    </Layout>
  );
}
