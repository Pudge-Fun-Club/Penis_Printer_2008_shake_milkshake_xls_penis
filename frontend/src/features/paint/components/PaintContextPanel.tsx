import { useRef } from "react";
import type { SceneObject } from "../../../api";
import Segmented from "../../../components/Segmented";
import { useI18n } from "../../../i18n";
import type { Tool } from "../PaintCanvas";
import type { ObjectOps } from "../hooks/useObjectOps";
import type { EraserBrush } from "../lib/eraser";
import type { FillStyle, VectorStyle } from "../lib/styling";
import { FillOptions } from "./FillOptions";
import { PaintStylePanel, type SelectedObjectSize } from "./PaintStylePanel";

/** Right-side context panel: history/clipboard actions, asset insertion, and
 * the per-tool section (arrange+style for select, brush size for erasers,
 * fill options for the fill tools). */
export default function PaintContextPanel({
  tool,
  activeToolLabel,
  ops,
  hasSelection,
  selectedObjects,
  selectedObjectSize,
  selectedObjectRotation,
  selectedStyle,
  sizeLinked,
  onSizeLinkedToggle,
  eraserBrush,
  onEraserBrushChange,
  eraserRadius,
  fillStyle,
  onFillStyleChange,
  onOpenGallery,
  onOpenMarkdown,
  onPickImage,
}: {
  tool: Tool;
  activeToolLabel: string;
  ops: ObjectOps;
  hasSelection: boolean;
  selectedObjects: SceneObject[];
  selectedObjectSize: SelectedObjectSize | null;
  selectedObjectRotation: number | null;
  selectedStyle: VectorStyle;
  sizeLinked: boolean;
  onSizeLinkedToggle: () => void;
  eraserBrush: EraserBrush;
  onEraserBrushChange: (brush: EraserBrush) => void;
  eraserRadius: number;
  fillStyle: FillStyle;
  onFillStyleChange: (patch: Partial<FillStyle>) => void;
  onOpenGallery: () => void;
  onOpenMarkdown: () => void;
  onPickImage: (file: File | undefined) => void;
}) {
  const { t } = useI18n();
  const imageInputRef = useRef<HTMLInputElement>(null);
  const isFillTool = tool === "bucketFill" || tool === "areaFill";

  return (
    <aside className="paint-context-panel">
      <div className="ctx-header">
        <div className="ctx-active-tool">
          <span className="muted">{t("paint.activeTool")}</span>
          <strong>{activeToolLabel}</strong>
        </div>
        <div className="paint-tools-actions ctx-actions">
          <button className="ghost" disabled={ops.history.undo === 0} onClick={ops.undo}
            title={t("paint.undo")} aria-label={t("paint.undo")}>↶</button>
          <button className="ghost" disabled={ops.history.redo === 0} onClick={ops.redo}
            title={t("paint.redo")} aria-label={t("paint.redo")}>↷</button>
          <button className="ghost" disabled={!hasSelection} onClick={ops.copySelected}
            title={hasSelection ? t("paint.copySelection") : t("paint.noSelection")} aria-label={t("paint.copy")}>⧉</button>
          <button className="ghost" disabled={!hasSelection} onClick={ops.cutSelected}
            title={hasSelection ? t("paint.cutSelection") : t("paint.noSelection")} aria-label={t("paint.cut")}>✂</button>
          <button className="ghost" disabled={ops.clipboardCount === 0} onClick={() => ops.pasteObjects()}
            title={ops.clipboardCount > 0 ? t("paint.pasteSelection") : t("paint.clipboardEmpty")} aria-label={t("paint.paste")}>
            ⎘{ops.clipboardCount > 1 ? <span className="act-count">{ops.clipboardCount}</span> : ""}
          </button>
          <button className="ghost" disabled={!hasSelection} onClick={ops.duplicateSelected}
            title={hasSelection ? t("paint.duplicateSelection") : t("paint.noSelection")} aria-label={t("paint.duplicate")}>⧉</button>
          <button className="ghost" disabled={selectedObjects.length < 2} onClick={() => ops.groupSelected()}
            title={selectedObjects.length >= 2 ? t("paint.groupSelection") : t("paint.needTwoObjects")} aria-label={t("paint.group")}>⊞</button>
          <button className="ghost" disabled={!selectedObjects.some((obj) => obj.groupId)} onClick={() => ops.ungroupSelected()}
            title={selectedObjects.some((obj) => obj.groupId) ? t("paint.ungroupSelection") : t("paint.noGroupSelected")} aria-label={t("paint.ungroup")}>⊟</button>
        </div>
        <div className="paint-asset-row">
          <button className="ghost" title={t("gallery.button")} aria-label={t("gallery.button")}
            onClick={onOpenGallery}>▦</button>
          <button className="ghost" title={t("paint.imageImport")} aria-label={t("paint.imageImport")}
            onClick={() => imageInputRef.current?.click()}>🖼</button>
          <button className="ghost" title={t("paint.md.button")} aria-label={t("paint.md.button")}
            onClick={onOpenMarkdown}>⌶</button>
        </div>
        <input
          ref={imageInputRef}
          type="file"
          accept="image/*"
          style={{ display: "none" }}
          onChange={(e) => { onPickImage(e.target.files?.[0]); e.target.value = ""; }}
        />
      </div>

      <div className="ctx-body" key={tool}>
        {tool === "select" && (
          <>
            <div className="paint-tool-section">
              <h4>{t("paint.section.arrange")}</h4>
              <div className="paint-tools-actions compact">
                <button className="ghost" disabled={!hasSelection} onClick={ops.fitSelected}
                  title={hasSelection ? t("paint.fitSelection") : t("paint.noSelection")} aria-label={t("paint.fit")}>⛶</button>
                <button className="ghost" disabled={!hasSelection} onClick={ops.centerSelected}
                  title={hasSelection ? t("paint.centerSelection") : t("paint.noSelection")} aria-label={t("paint.center")}>⌖</button>
                <button className="ghost" disabled={!hasSelection} onClick={() => ops.moveSelected(-1)}
                  title={hasSelection ? t("paint.moveBack") : t("paint.noSelection")} aria-label={t("paint.toBack")}>⤓</button>
                <button className="ghost" disabled={!hasSelection} onClick={() => ops.moveSelected(1)}
                  title={hasSelection ? t("paint.moveFront") : t("paint.noSelection")} aria-label={t("paint.toFront")}>⤒</button>
                <button className="ghost" disabled={!hasSelection} onClick={ops.deleteSelected}
                  title={hasSelection ? t("paint.deleteSelection") : t("paint.noSelection")} aria-label={t("paint.delete")}>
                  🗑{selectedObjects.length > 1 ? <span className="act-count">{selectedObjects.length}</span> : ""}
                </button>
                <button className="ghost" disabled={!hasSelection} onClick={ops.convertSelectedToLines}
                  title={hasSelection ? t("paint.convertToLines") : t("paint.noSelection")} aria-label={t("paint.convertToLines")}>⇄</button>
              </div>
            </div>
            <PaintStylePanel
              hasSelection={hasSelection}
              selectedObjectSize={selectedObjectSize}
              selectedObjectRotation={selectedObjectRotation}
              selectedStyle={selectedStyle}
              sizeLinked={sizeLinked}
              onSizeLinkedToggle={onSizeLinkedToggle}
              onWidthChange={(v) => ops.setSelectedObjectSize("width", v)}
              onHeightChange={(v) => ops.setSelectedObjectSize("height", v)}
              onRotationChange={ops.setSelectedObjectRotation}
              onStyleChange={ops.updateSelectedStyle}
            />
          </>
        )}

        {(tool === "erase" || tool === "eraseLine") && (
          <div className="paint-tool-section">
            <h4>{t("paint.section.erase")}</h4>
            <Segmented<EraserBrush>
              value={eraserBrush}
              onChange={onEraserBrushChange}
              options={[
                { value: "point", label: t("paint.coloringBrushPoint"), title: t("paint.coloringBrushPoint") },
                { value: "small",  label: t("paint.coloringBrushSmall"),  title: t("paint.coloringBrushSize") },
                { value: "medium", label: t("paint.coloringBrushMedium"), title: t("paint.coloringBrushSize") },
                { value: "large",  label: t("paint.coloringBrushLarge"),  title: t("paint.coloringBrushSize") },
              ]}
              className="paint-tool-grid"
            />
            {eraserBrush !== "point" && (
              <div className="coloring-brush-hint">⌀ {Math.round(eraserRadius * 2)} mm</div>
            )}
          </div>
        )}

        {isFillTool && (
          <div className="paint-tool-section">
            <h4>{t("paint.fillOptions")}</h4>
            <FillOptions value={fillStyle} onChange={onFillStyleChange} />
          </div>
        )}
      </div>
    </aside>
  );
}
