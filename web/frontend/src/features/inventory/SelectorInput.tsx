import { Input, Radio, Select, Space } from "antd";
export function SelectorInput({
  label,
  options = [],
  mode,
  names,
  expression,
  onMode,
  onNames,
  onExpression,
}: {
  label: string;
  options?: string[];
  mode: "literal" | "expression";
  names: string[];
  expression: string;
  onMode: (v: "literal" | "expression") => void;
  onNames: (v: string[]) => void;
  onExpression: (v: string) => void;
}) {
  return (
    <div className="selector-field">
      <label>{label}</label>
      <Radio.Group
        aria-label={`${label}输入方式`}
        value={mode}
        onChange={(e) => onMode(e.target.value)}
        options={[
          { label: "名称选择", value: "literal" },
          { label: "专家表达式", value: "expression" },
        ]}
      />
      {mode === "literal" ? (
        <Select
          aria-label={`${label}名称`}
          mode="tags"
          options={options.map((value) => ({ value, label: value }))}
          virtual={false}
          value={names}
          onChange={onNames}
          placeholder="选择候选或输入完整名称后回车；留空表示全部"
          style={{ width: "100%" }}
        />
      ) : (
        <Input
          aria-label={`${label}表达式`}
          value={expression}
          onChange={(e) => onExpression(e.target.value)}
          placeholder="输入 Batfish specifier；留空表示全部"
        />
      )}
      <small className="muted">
        当前按
        {mode === "literal" ? "完整名称匹配，不解释正则符号" : "专家表达式匹配"}
        。
      </small>
    </div>
  );
}
