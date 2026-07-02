import Segmented from "../../../components/Segmented";
import { useI18n } from "../../../i18n";
import type { Tool } from "../PaintCanvas";

interface ToolMeta {
  value: Tool;
  label: string;
  icon: string;
}

/** All paint tools with their icons; the rail groups them by purpose. */
export function paintTools(t: (key: string) => string): ToolMeta[] {
  return [
    { value: "select", label: t("paint.tool.select"), icon: "⬚" },
    { value: "pen", label: t("paint.tool.pen"), icon: "✎" },
    { value: "erase", label: t("paint.tool.erase"), icon: "⌫" },
    { value: "eraseLine", label: t("paint.tool.eraseLine"), icon: "✂" },
    { value: "line", label: t("paint.tool.line"), icon: "╱" },
    { value: "rect", label: t("paint.tool.rect"), icon: "▭" },
    { value: "maskRect", label: t("paint.tool.maskRect"), icon: "▰" },
    { value: "circle", label: t("paint.tool.circle"), icon: "◯" },
    { value: "semicircle", label: t("paint.tool.semicircle"), icon: "◗" },
    { value: "text", label: t("paint.tool.text"), icon: "T" },
    { value: "bucketFill", label: t("paint.tool.bucketFill"), icon: "🪣" },
    { value: "areaFill", label: t("paint.tool.areaFill"), icon: "▨" },
    { value: "maskCircle", label: t("paint.tool.maskCircle"), icon: "●" },
  ];
}

const GROUPS: Tool[][] = [
  ["select"],
  ["pen", "line", "rect", "circle", "semicircle", "text"],
  ["bucketFill", "areaFill"],
  ["maskRect", "maskCircle"],
  ["erase", "eraseLine"],
];

/** Vertical tool rail on the left edge of the canvas, one segmented control
 * per tool group (select / draw / fill / mask / erase). */
export default function PaintToolRail({
  tool,
  onToolChange,
}: {
  tool: Tool;
  onToolChange: (tool: Tool) => void;
}) {
  const { t } = useI18n();
  const tools = paintTools(t);
  const groups = GROUPS.map((members) => tools.filter((o) => members.includes(o.value)));
  return (
    <nav className="paint-tool-rail" aria-label={t("paint.activeTool")}>
      {groups.map((group, gi) => (
        <span key={gi} style={{ display: "contents" }}>
          {gi > 0 && <span className="rail-div" />}
          <div className="rail-group" style={{ flex: group.length }}>
            <Segmented<Tool> value={tool} onChange={onToolChange}
              options={group.map((o) => ({ value: o.value, label: o.icon, title: o.label }))}
              className="paint-tool-grid vertical" />
          </div>
        </span>
      ))}
    </nav>
  );
}
