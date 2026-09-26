import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import { ConfigProvider, theme as antTheme, type ThemeConfig } from "antd";
import zhCN from "antd/locale/zh_CN";
import { DesktopOutlined, MoonOutlined, SunOutlined } from "@ant-design/icons";

type Preference = "light" | "dark" | "system";
type Mode = "light" | "dark";
const storageKey = "batfish-theme-preference";
export const palettes = {
  light: {
    bg: "#eff3f9",
    panel: "#ffffff",
    raised: "#f6f8fc",
    input: "#ffffff",
    text: "#1d2a42",
    muted: "#5c6d85",
    border: "#8492a7",
    divider: "#dce4ef",
    accent: "#3e57d9",
    accentBg: "#ebefff",
    cyan: "#007e85",
    good: "#147551",
    goodBg: "#e8f6ef",
    warning: "#875715",
    warningBg: "#fff7e9",
    selected: "#edf2ff",
    shadow: "0 12px 36px #253b6410",
    highlight: "#fff0c2",
  },
  dark: {
    bg: "#0a111e",
    panel: "#111d2e",
    raised: "#19273b",
    input: "#0d1829",
    text: "#e6edf9",
    muted: "#a0b1ca",
    border: "#62738d",
    divider: "#2a3b54",
    accent: "#a0b2ff",
    accentBg: "#243560",
    cyan: "#6addd8",
    good: "#66dfb2",
    goodBg: "#143c35",
    warning: "#f4c780",
    warningBg: "#322a20",
    selected: "#1b2d4d",
    shadow: "0 16px 42px #0000001a",
    highlight: "#453b22",
  },
} as const;
function storedPreference(): Preference {
  try {
    const value = localStorage.getItem(storageKey);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}
function systemMode(): Mode {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}
const ThemeContext = createContext<{
  preference: Preference;
  choose: (value: Preference) => void;
}>({ preference: "system", choose: () => {} });

export function ThemeProvider({ children }: PropsWithChildren) {
  const [preference, setPreference] = useState<Preference>(storedPreference);
  const [system, setSystem] = useState<Mode>(systemMode);
  const mode = preference === "system" ? system : preference;
  useEffect(() => {
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    const update = () => setSystem(systemMode());
    media?.addEventListener("change", update);
    update();
    return () => media?.removeEventListener("change", update);
  }, []);
  useLayoutEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = mode;
    root.style.colorScheme = mode;
    root.style.backgroundColor = palettes[mode].bg;
    for (const [name, value] of Object.entries(palettes[mode]))
      root.style.setProperty(`--app-${name}`, value);
  }, [mode]);
  const config = useMemo<ThemeConfig>(() => {
    const p = palettes[mode];
    return {
      algorithm:
        mode === "dark" ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
      token: {
        colorPrimary: p.accent,
        colorLink: p.accent,
        colorInfo: p.accent,
        colorSuccess: p.good,
        colorSuccessBg: p.goodBg,
        colorWarning: p.warning,
        colorWarningBg: p.warningBg,
        colorInfoBg: p.accentBg,
        colorBgLayout: p.bg,
        colorBgContainer: p.panel,
        colorBgElevated: p.raised,
        colorText: p.text,
        colorTextSecondary: p.muted,
        colorTextPlaceholder: p.muted,
        colorBorder: p.border,
        colorBorderSecondary: p.divider,
        borderRadius: 8,
        fontSize: 14,
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif',
      },
      components: {
        Layout: { headerBg: p.panel, siderBg: "#0f192a" },
        Menu: { itemBorderRadius: 7, itemHeight: 44 },
        Button: {
          primaryColor: "#ffffff",
          colorPrimary: "#4158d7",
          colorPrimaryHover: "#344ac1",
          colorPrimaryActive: "#2b3da8",
          defaultHoverColor: p.accent,
          defaultActiveColor: p.accent,
          defaultHoverBorderColor: p.accent,
          defaultActiveBorderColor: p.accent,
        },
        Checkbox: { colorPrimary: "#4158d7", colorPrimaryHover: "#344ac1" },
        Radio: { colorPrimary: "#4158d7", colorPrimaryHover: "#344ac1" },
        Table: {
          headerBg: p.raised,
          headerColor: p.muted,
          rowHoverBg: p.selected,
          borderColor: p.divider,
          cellPaddingBlock: 15,
        },
        Card: { headerFontSize: 14 },
        Input: { colorBgContainer: p.input },
        Select: { colorBgContainer: p.input, optionSelectedBg: p.selected },
      },
    };
  }, [mode]);
  const value = useMemo(
    () => ({
      preference,
      choose: (next: Preference) => {
        setPreference(next);
        try {
          localStorage.setItem(storageKey, next);
        } catch {
          /* Theme remains usable with storage blocked. */
        }
      },
    }),
    [preference],
  );
  return (
    <ThemeContext.Provider value={value}>
      <ConfigProvider
        locale={zhCN}
        theme={config}
        button={{ autoInsertSpace: false }}
      >
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}

export function ThemeControl() {
  const { preference, choose } = useContext(ThemeContext);
  return (
    <div className="theme-control" role="group" aria-label="外观主题">
      {(
        [
          { value: "light", label: "浅色主题", icon: <SunOutlined /> },
          { value: "dark", label: "深色主题", icon: <MoonOutlined /> },
          { value: "system", label: "跟随系统", icon: <DesktopOutlined /> },
        ] as const
      ).map((item) => (
        <button
          key={item.value}
          type="button"
          title={item.label}
          aria-label={item.label}
          aria-pressed={preference === item.value}
          onClick={() => choose(item.value)}
        >
          {item.icon}
        </button>
      ))}
    </div>
  );
}
