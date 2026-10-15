import { req } from "./req";

export interface NotesStatus {
  ocrReady: boolean;
  ocrModel: string;
  penCalibrated: boolean;
  paperCalibrated: boolean;
  width: number;
  height: number;
  fonts: { id: string; label: string }[];
  paperStack?: {
    profileId: string; fingerprint: string;
    thicknessMm: number; penDownZ: number; penUpZ: number;
  };
}
export interface NotesOptions {
  text: string;
  font: string;
  size: number;
  margin: number;
  line_spacing: number;
}
export interface NotesSheet {
  number: number;
  text: string;
  width: number;
  height: number;
  polylines: number[][][];
  svg?: string;
  optimization?: {
    beforeStrokes: number; afterStrokes: number;
    beforeTravelMm: number; afterTravelMm: number;
    beforePoints: number; afterPoints: number;
  };
  plotStats?: {
    estimatedSeconds: number; penLifts: number;
    drawMm: number; travelMm: number; penLiftMm: number;
  };
}
export interface NotesPreview {
  pages: NotesSheet[];
  profile: { id: string; name: string; fingerprint: string };
  warnings: string[];
  jobs?: { number: number; filename: string | null }[];
  regions?: { text: string; box: number[] }[];
}
export interface VectorOptions { id: string; font: string; margin: number }
const json = (body: unknown) => ({
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});
export interface NextSheetOptions { thickness_mm: number; profile_id: string; fingerprint: string }
export const notesClient = {
  notesStatus: () => req<NotesStatus>("/api/notes/status"),
  notesNextSheet: (options: NextSheetOptions) => req<NotesStatus>("/api/notes/next-sheet", json(options)),
  notesVectorize: (file: File, straighten = false, detail = 3) => {
    const body = new FormData();
    body.append("file", file);
    body.append("straighten", String(straighten));
    body.append("detail", String(detail));
    return req<{ id: string; width: number; height: number; strokes: number }>(
      "/api/notes/vectorize", { method: "POST", body });
  },
  notesVectorPreview: (options: VectorOptions) =>
    req<NotesPreview>("/api/notes/vector-preview", json(options)),
  notesVectorJobs: (options: VectorOptions) =>
    req<NotesPreview>("/api/notes/vector-jobs", json(options)),
  notesPreview: (options: NotesOptions) => req<NotesPreview>("/api/notes/preview", json(options)),
  notesJobs: (options: NotesOptions) => req<NotesPreview>("/api/notes/jobs", json(options)),
  notesTranscribe: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return req<{ text: string; warnings: string[] }>("/api/notes/transcribe", { method: "POST", body });
  },
  notesOcrSettings: (api_key: string, model: string) =>
    req<{ ocrReady: boolean; ocrModel: string }>("/api/notes/ocr-settings", {
      ...json({ api_key, model }), method: "PUT",
    }),
};
