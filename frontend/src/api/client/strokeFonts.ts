import { req, reqBlob } from "./req";
import type {
  StrokeFontDocument,
  StrokeFontListResponse,
  StrokeFontResponse,
  StrokeFontSummary,
} from "../types/strokeFonts";

const json = (body: unknown): RequestInit => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

const SAFE_NAME = /[^A-Za-z0-9_.-]+/g;

// Fetch the .gcsfont backup and trigger a browser download.
async function downloadStrokeFont(id: string, label: string): Promise<void> {
  const blob = await reqBlob(`/api/stroke-fonts/${encodeURIComponent(id)}/export`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${(label || "font").replace(SAFE_NAME, "-").replace(/^[-.]+|[-.]+$/g, "") || "font"}.gcsfont`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

interface StrokeFontImportResponse {
  strokeFont: StrokeFontDocument;
  strokeFonts: StrokeFontSummary[];
}

export const strokeFontsClient = {
  listStrokeFonts: () => req<StrokeFontListResponse>("/api/stroke-fonts"),
  createStrokeFont: (label: string) =>
    req<StrokeFontResponse>("/api/stroke-fonts", { method: "POST", ...json({ label }) }),
  getStrokeFont: (id: string) =>
    req<StrokeFontResponse>(`/api/stroke-fonts/${encodeURIComponent(id)}`),
  saveStrokeFont: (id: string, document: StrokeFontDocument) =>
    req<StrokeFontResponse>(`/api/stroke-fonts/${encodeURIComponent(id)}`, {
      method: "PUT",
      ...json(document),
    }),
  deleteStrokeFont: (id: string) =>
    req<StrokeFontListResponse>(`/api/stroke-fonts/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  exportStrokeFont: (id: string, label: string) => downloadStrokeFont(id, label),
  importStrokeFont: (file: File) => {
    const body = new FormData();
    body.set("file", file);
    return req<StrokeFontImportResponse>("/api/stroke-fonts/import", { method: "POST", body });
  },
};
