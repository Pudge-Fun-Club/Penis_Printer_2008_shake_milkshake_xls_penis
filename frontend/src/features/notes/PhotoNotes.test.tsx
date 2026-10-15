// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import PhotoNotes from "./PhotoNotes";

const mocks = vi.hoisted(() => ({
  notesStatus: vi.fn(), notesVectorize: vi.fn(), notesVectorPreview: vi.fn(),
  notesVectorJobs: vi.fn(), position: vi.fn(), send: vi.fn(), jobCommand: vi.fn(),
  notesNextSheet: vi.fn(),
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
    fonts: [{ id: "notes-neat", label: "Аккуратный" }],
    paperStack: { profileId: "p", fingerprint: "v1", thicknessMm: 0.1, penDownZ: 1.4, penUpZ: 7.4 } });
  mocks.position.mockResolvedValue({ homed: true });
  mocks.notesVectorize.mockResolvedValue({ id: "a".repeat(24), strokes: 3 });
  mocks.notesVectorPreview.mockResolvedValue(preview);
  mocks.notesVectorJobs.mockResolvedValue({ ...preview,
    jobs: [{ number: 1, filename: "page.gcode" }] });
  mocks.send.mockResolvedValue({ done: true });
  URL.createObjectURL = vi.fn(() => "blob:test");
  URL.revokeObjectURL = vi.fn();
});

it("lowers the stack on confirmation and rebuilds SVG without starting the printer", async () => {
  app();
  await vectorize();
  fireEvent.click(screen.getByLabelText("Ручка установлена, чистый лист закреплён"));
  mocks.notesNextSheet.mockResolvedValue({ ...(await mocks.notesStatus()),
    paperStack: { profileId: "p", fingerprint: "v2", thicknessMm: 0.12, penDownZ: 1.28, penUpZ: 7.28 } });
  fireEvent.change(screen.getByLabelText("Толщина одного листа, мм"), { target: { value: "0.12" } });
  fireEvent.click(screen.getByRole("button", { name: "Лист убран — следующий" }));
  await screen.findByText(/Высота касания: 1,28 мм/);
  expect(mocks.notesNextSheet).toHaveBeenCalledWith({ thickness_mm: 0.12, profile_id: "p", fingerprint: "v1" });
  expect(mocks.notesVectorPreview).toHaveBeenCalledTimes(2);
  expect((screen.getByLabelText("Ручка установлена, чистый лист закреплён") as HTMLInputElement).checked).toBe(false);
  expect((screen.getByRole("button", { name: "Написать SVG" }) as HTMLButtonElement).disabled).toBe(true);
  expect(mocks.send).not.toHaveBeenCalled();
});

it("disables physical sheet adjustment while printing or paused", async () => {
  render(<PhotoNotes visible status={{ online: true, job: { state: "Paused" } }} onAction={vi.fn()} onSetup={vi.fn()} />);
  const button = await screen.findByRole("button", { name: "Лист убран — следующий" });
  expect((button as HTMLButtonElement).disabled).toBe(true);
});

it("refreshes stack heights when returning from manual notes", async () => {
  app();
  await screen.findByText(/Высота касания: 1,4 мм/);
  fireEvent.click(screen.getByRole("button", { name: "Ввести текст вручную" }));
  await screen.findByLabelText("Текст конспекта");
  mocks.notesStatus.mockResolvedValue({ ...(await mocks.notesStatus()),
    paperStack: { profileId: "p", fingerprint: "v2", thicknessMm: 0.1, penDownZ: 1.3, penUpZ: 7.3 } });
  fireEvent.click(screen.getByRole("button", { name: /Фото целой страницы/ }));
  await screen.findByText(/Высота касания: 1,3 мм/);
});

it("shows a failed sheet adjustment and leaves printing unconfirmed", async () => {
  app();
  await vectorize();
  mocks.notesNextSheet.mockRejectedValue(new Error("Высота выйдет за пределы Z"));
  fireEvent.click(screen.getByRole("button", { name: "Лист убран — следующий" }));
  expect((await screen.findByRole("alert")).textContent).toContain("за пределы Z");
  expect((screen.getByRole("button", { name: "Написать SVG" }) as HTMLButtonElement).disabled).toBe(true);
  expect(mocks.send).not.toHaveBeenCalled();
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

it("shows print time, lifts and travel and can reveal pen-up routes", async () => {
  mocks.notesVectorPreview.mockResolvedValue({ ...preview, pages: [{ ...sheet,
    polylines: [[[5, 5], [8, 8]], [[12, 12], [15, 15]]],
    optimization: { beforeStrokes: 740, afterStrokes: 111,
      beforeTravelMm: 23928.4, afterTravelMm: 698.2, beforePoints: 7106, afterPoints: 3740 },
    plotStats: { estimatedSeconds: 247, penLifts: 111, drawMm: 1920,
      travelMm: 698, penLiftMm: 3 },
  }] });
  app();
  await vectorize();
  expect(screen.getByText(/4 мин 7 с/)).toBeTruthy();
  expect(screen.getByText(/740 → 111/)).toBeTruthy();
  expect(screen.getByText(/23,93 м → 0,70 м/)).toBeTruthy();
  fireEvent.click(screen.getByLabelText("Показать переходы ручки"));
  expect(screen.getByLabelText("Переходы с поднятой ручкой").getAttribute("d")).toContain("M8,8L12,12");
});
