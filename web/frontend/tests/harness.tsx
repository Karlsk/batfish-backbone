import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Card, Input, Button } from "antd";
import { Providers, Shell } from "../src/app/App";
import { useResourceContext, resourceKey } from "../src/app/context";
import { AdvancedOptions } from "../src/components/AdvancedOptions";
import { DetailsDrawer } from "../src/components/DetailsDrawer";
function Harness() {
  const { selectNetwork, selectSnapshot, network, snapshot } =
    useResourceContext();
  const [value, setValue] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => {
    selectNetwork({
      id: "n",
      name: "华东区域核心网络与跨数据中心测试环境中文长名称",
    });
  }, []);
  useEffect(() => {
    if (network && !snapshot)
      selectSnapshot({
        id: "s",
        networkId: "n",
        name: "生产变更前备份配置快照中文长名称二零二六年九月",
      });
  }, [network, snapshot]);
  return (
    <Shell>
      <div className="harness" style={{ minHeight: 1500 }}>
        <Card title="渐进展示 · 组件验证">
          <p>此页面仅用于组件验收，使用合成上下文。</p>
          <AdvancedOptions activeCount={value ? 1 : 0}>
            <label htmlFor="source">源地址</label>
            <Input
              id="source"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder="可选"
            />
          </AdvancedOptions>
          <Button onClick={() => setOpen(true)}>查看详情</Button>
          <DetailsDrawer
            open={open}
            title="参数详情"
            onClose={() => setOpen(false)}
            queryKey={resourceKey(
              null,
              { networkId: "n", snapshotId: "s" },
              "example",
              { value },
            )}
            load={async () => ({ source_ip: value })}
          />
        </Card>
      </div>
    </Shell>
  );
}
createRoot(document.getElementById("root")!).render(
  <Providers>
    <BrowserRouter>
      <Harness />
    </BrowserRouter>
  </Providers>,
);
