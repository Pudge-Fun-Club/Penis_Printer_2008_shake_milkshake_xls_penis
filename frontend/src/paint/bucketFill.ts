import { simplify, type Pt } from "./geometry";

export interface BucketFillOptions {
  /** Raster resolution in pixels per mm. Higher = more precise but slower. */
  scale?: number;
  /** Stroke wall thickness in mm (bridges tiny anti-aliasing gaps). */
  wall?: number;
}

/**
 * Paint-bucket region detection. Rasterises the given world-space polylines as
 * "walls" onto an offscreen canvas, flood-fills the empty pixels reachable from
 * `seed`, and traces the outer boundary of that blob back into an mm-space
 * polygon. Returns `null` when the seed is on a wall or the region leaks to the
 * canvas edge (i.e. it is not enclosed).
 */
export function bucketFillRegion(
  worldLines: Pt[][],
  seed: Pt,
  W: number,
  H: number,
  opts: BucketFillOptions = {}
): Pt[] | null {
  const scale = opts.scale ?? 3;
  const wall = opts.wall ?? 0.6;
  const pw = Math.max(1, Math.round(W * scale));
  const ph = Math.max(1, Math.round(H * scale));

  const canvas = document.createElement("canvas");
  canvas.width = pw;
  canvas.height = ph;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;

  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, pw, ph);
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = Math.max(1, wall * scale);
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  for (const line of worldLines) {
    if (line.length < 2) continue;
    ctx.beginPath();
    ctx.moveTo(line[0][0] * scale, line[0][1] * scale);
    for (let i = 1; i < line.length; i++) ctx.lineTo(line[i][0] * scale, line[i][1] * scale);
    ctx.stroke();
  }

  const img = ctx.getImageData(0, 0, pw, ph).data;
  const isWall = (x: number, y: number) => img[(y * pw + x) * 4] > 127; // red channel of a white stroke

  const sx = Math.round(seed[0] * scale);
  const sy = Math.round(seed[1] * scale);
  if (sx < 0 || sy < 0 || sx >= pw || sy >= ph || isWall(sx, sy)) return null;

  // Scanline flood-fill across non-wall pixels.
  const filled = new Uint8Array(pw * ph);
  const stack: number[] = [sx, sy];
  let leaked = false;
  while (stack.length) {
    const y = stack.pop()!;
    let x = stack.pop()!;
    while (x > 0 && !isWall(x - 1, y) && !filled[y * pw + (x - 1)]) x--;
    let up = false;
    let down = false;
    for (; x < pw && !isWall(x, y) && !filled[y * pw + x]; x++) {
      filled[y * pw + x] = 1;
      if (x === 0 || y === 0 || x === pw - 1 || y === ph - 1) leaked = true;
      if (y > 0 && !isWall(x, y - 1) && !filled[(y - 1) * pw + x]) {
        if (!up) { stack.push(x, y - 1); up = true; }
      } else up = false;
      if (y < ph - 1 && !isWall(x, y + 1) && !filled[(y + 1) * pw + x]) {
        if (!down) { stack.push(x, y + 1); down = true; }
      } else down = false;
    }
  }
  if (leaked) return null;

  const contour = traceBoundary(filled, pw, ph, sx, sy);
  if (!contour || contour.length < 4) return null;

  const mm = contour.map<Pt>(([x, y]) => [x / scale, y / scale]);
  const poly = simplify(mm, 0.5);
  if (poly.length < 3) return null;
  poly.push(poly[0]); // close it so styling.closedLine() detects the polygon
  return poly;
}

/**
 * Moore-neighbour boundary trace of a filled blob. Walks the pixel border
 * clockwise from the top-most/left-most filled pixel and returns its outline.
 */
function traceBoundary(filled: Uint8Array, w: number, h: number, sx: number, sy: number): Pt[] | null {
  const at = (x: number, y: number) => x >= 0 && y >= 0 && x < w && y < h && filled[y * w + x] === 1;

  // Find a guaranteed boundary start: walk up from the seed to the top edge of the blob.
  let startX = sx;
  let startY = sy;
  while (at(startX, startY - 1)) startY--;

  // 8-neighbour offsets, clockwise starting from "up".
  const dirs = [
    [0, -1], [1, -1], [1, 0], [1, 1],
    [0, 1], [-1, 1], [-1, 0], [-1, -1],
  ];
  const out: Pt[] = [];
  let cx = startX;
  let cy = startY;
  let dir = 6; // came from the left; start scanning from "up-ish"
  const maxSteps = w * h * 4;
  for (let step = 0; step < maxSteps; step++) {
    out.push([cx, cy]);
    let found = false;
    // Scan neighbours clockwise starting just after the direction we came from.
    for (let k = 0; k < 8; k++) {
      const d = (dir + 6 + k) % 8;
      const nx = cx + dirs[d][0];
      const ny = cy + dirs[d][1];
      if (at(nx, ny)) {
        cx = nx;
        cy = ny;
        dir = d;
        found = true;
        break;
      }
    }
    if (!found) break; // isolated pixel
    if (cx === startX && cy === startY && out.length > 2) break;
  }
  return out.length >= 4 ? out : null;
}
