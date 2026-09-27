import { useEffect, type PropsWithChildren } from "react";
import { Button, Layout, Space, Typography } from "antd";
import { ArrowRightOutlined, RadarChartOutlined } from "@ant-design/icons";
import { Link, useLocation } from "react-router-dom";
import { ThemeControl } from "../../app/theme";
import { ServiceStatus } from "../../app/ServiceStatus";
import { chooseEntry } from "../../app/entry";
import { useResourceContext } from "../../app/context";
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

export function LeaderOverview() {
  const { network, snapshot } = useResourceContext();
  return (
    <>
      <div className="leader-hero">
        <div className="leader-hero-orbit" aria-hidden="true" />
        <div className="leader-hero-content">
          <span className="leader-kicker">NETWORK INSIGHT / 日常总览</span>
          <Typography.Title level={1}>
            看清网络，从可靠的检查开始。
          </Typography.Title>
          <p>
            这里将汇集所有共享网络的检查结论。每项结论都可以逐级查看影响范围、证据和技术详情。
          </p>
        </div>
        <div className="leader-hero-index" aria-hidden="true">
          01 / OVERVIEW
        </div>
      </div>
      <section
        className="leader-status-card"
        aria-labelledby="leader-empty-title"
      >
        <div className="leader-status-symbol" aria-hidden="true">
          —
        </div>
        <div>
          <div className="leader-kicker">当前状态 / AWAITING CHECK</div>
          <Typography.Title id="leader-empty-title" level={2}>
            尚未检查
          </Typography.Title>
          <p>
            尚无可用于生成业务结论的检查结果。检查与跨网络汇总将在后续步骤接入；当前不显示健康分或影响判断。
          </p>
          {network && (
            <p className="leader-context-note">
              技术工作台当前选择：{network.name}
              {snapshot ? ` / ${snapshot.name}` : " / 尚未选择快照"}
            </p>
          )}
          <Link to="/networks" onClick={() => chooseEntry("technical")}>
            <Button
              type="primary"
              icon={<ArrowRightOutlined />}
              iconPlacement="end"
            >
              查看网络与快照
            </Button>
          </Link>
        </div>
      </section>
      <p className="leader-footnote">
        基于已上传配置进行模型分析；页面不代表在线监控或实际设备状态。
      </p>
    </>
  );
}
