import type { SceneObject } from "../../../../api";
import { IDENTITY, toMultiPath, type Pt, type Transform } from "../../lib/geometry";

function objTransform(t: Transform) {
  const sx = t.scaleX ?? t.scale;
  const sy = t.scaleY ?? t.scale;
  return `translate(${t.x} ${t.y}) rotate(${(t.rotation * 180) / Math.PI}) scale(${sx},${sy})`;
}

/** Renders every scene object (z-sorted) as one merged path each; masks get
 * their dashed cover style, plotted objects fade out. Pure display layer —
 * pointer events are handled by the selection layer above. */
export default function ObjectsLayer({
  objects,
  selectedIds,
  stroke,
}: {
  objects: SceneObject[];
  selectedIds: string[];
  stroke: number;
}) {
  return (
    <>
      {objects.map((obj) => {
        const t = obj.transform ?? IDENTITY;
        const strokeScale = Math.max(t.scaleX ?? t.scale, t.scaleY ?? t.scale);
        const isMask = obj.type === "mask-rect" || obj.data?.mask === "erase";
        return (
          <g
            key={obj.id}
            transform={objTransform(t)}
            opacity={obj.plotted ? 0.25 : 1}
            style={{ pointerEvents: "none" }}
          >
            {isMask ? (
              <path d={toMultiPath((obj.cachedPolylines ?? []) as Pt[][])}
                fill="#101013" fillOpacity={0.92}
                stroke={selectedIds.includes(obj.id) ? "var(--accent)" : "rgba(255,255,255,0.45)"}
                strokeWidth={stroke / strokeScale}
                strokeDasharray={`${(stroke * 2) / strokeScale} ${stroke / strokeScale}`}
                strokeLinejoin="round" strokeLinecap="round" />
            ) : (
              // One merged path per object — all lines share the same stroke.
              <path d={toMultiPath((obj.cachedPolylines ?? []) as Pt[][])} fill="none"
                stroke={obj.plotted ? "var(--muted)" : "var(--busy)"}
                strokeWidth={stroke / strokeScale} strokeLinejoin="round" strokeLinecap="round" />
            )}
          </g>
        );
      })}
    </>
  );
}
