import { Collapse, Tag } from "antd";
import type { PropsWithChildren } from "react";
export function AdvancedOptions({
  activeCount,
  children,
}: PropsWithChildren<{ activeCount: number }>) {
  return (
    <Collapse
      className="advanced-options"
      destroyOnHidden={false}
      items={[
        {
          key: "options",
          label: (
            <span>
              高级参数{" "}
              <Tag>
                {activeCount ? `已生效 ${activeCount} 项` : "使用默认值"}
              </Tag>
            </span>
          ),
          children,
          forceRender: true,
        },
      ]}
    />
  );
}
