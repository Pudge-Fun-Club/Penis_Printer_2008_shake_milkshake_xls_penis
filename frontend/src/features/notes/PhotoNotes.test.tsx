// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import PhotoNotes from "./PhotoNotes";

const mocks = vi.hoisted(() => ({
  notesStatus: vi.fn(), notesVectorize: vi.fn(), notesVectorPreview: vi.fn(),
  notesVectorJobs: vi.fn(), position: vi.fn(), send: vi.fn(), jobCommand: vi.fn(),
}));
vi.mock("../../api", () => ({ api: mocks }));
const sheet = { number: 1, text: "", width: 160, height: 160,
  svg: '<svg xmlns="http://www.w3.org/2000/svg"><path d="M5,5L8,8"/></svg>',
  polylines: [[[5, 5], [8, 8]]] };
const preview = { pages: [sheet], profile: { id: "p", fingerprint: "v1" }, warnings: [] };

beforeEach(() => {
  Object.values(mocks).forEach(m => m.mockReset());
  mocks.notesStatus.mockResolvedValue({ ocrReady: false, ocrModel: "gpt-4.1-mini",
    penCalibrated: true, paperCalibrated: true, width: 160, height: 160,
    fonts: [{ id: "notes-neat", label: "Аккуратный" }] });
  mocks.position.mockResolvedValue({ homed: true });
  mocks.notesVectorize.mockResolvedValue({ id: "a".repeat(24), strokes: 3 });
  mocks.notesVectorPreview.mockResolvedValue(preview);
  mocks.notesVectorJobs.mockResolvedValue({ ...preview,
    jobs: [{ number: 1, filename: "page.gcode" }] });
  mocks.send.mockResolvedValue({ done: true });
  URL.createObjectURL = vi.fn(() => "blob:test");
  URL.revokeObjectURL = vi.fn();
});
afterEach(cleanup);

function app() {
  render(<PhotoNotes visible status={{ online: true, job: null }} onAction={vi.fn()} onSetup={vi.fn()} />);
}
async function vectorize() {
  await screen.findByText("Как на фото");
  fireEvent.change(screen.getByLabelText("Фото страницы"), {
    target: { files: [new File(["image"], "page.png", { type: "image/png" })] },
  });
  fireEvent.click(screen.getByRole("button", { name: "Сделать SVG" }));
  await screen.findByRole("link", { name: "Скачать SVG" });
}

it("vectorizes the whole photo without needing an OCR key", async () => {
  app();
  await vectorize();
  expect(mocks.notesVectorize).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText("Предпросмотр SVG")).toBeTruthy();
});

it("prints the exact SVG preview geometry", async () => {
  app();
  await vectorize();
  fireEvent.click(screen.getByLabelText("Ручка установлена, чистый лист закреплён"));
  fireEvent.click(screen.getByRole("button", { name: "Написать SVG" }));
  await waitFor(() => expect(mocks.send).toHaveBeenCalledWith("page.gcode", true));
});

it("requires review again if printing profile changes", async () => {
  mocks.notesVectorJobs.mockResolvedValue({ ...preview,
    profile: { id: "p", fingerprint: "v2" }, jobs: [{ number: 1, filename: "new.gcode" }] });
  app();
  await vectorize();
  fireEvent.click(screen.getByLabelText("Ручка установлена, чистый лист закреплён"));
  fireEvent.click(screen.getByRole("button", { name: "Написать SVG" }));
  await screen.findByRole("alert");
  expect(mocks.send).not.toHaveBeenCalled();
});
