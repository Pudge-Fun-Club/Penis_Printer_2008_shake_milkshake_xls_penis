// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import Notes from "./Notes";

const mocks = vi.hoisted(() => ({
  notesStatus: vi.fn(), notesPreview: vi.fn(), notesJobs: vi.fn(),
  notesTranscribe: vi.fn(), notesOcrSettings: vi.fn(), send: vi.fn(),
  jobCommand: vi.fn(), position: vi.fn(),
  notesNextSheet: vi.fn(),
}));
vi.mock("../../api", () => ({ api: mocks }));

const sheet = { number: 1, text: "Привет", width: 160, height: 160,
  polylines: [[[5, 5], [8, 8]]] };
const status = { ocrReady: true, ocrModel: "gpt-4.1-mini", penCalibrated: true,
  paperCalibrated: true, width: 160, height: 160,
  fonts: [{ id: "notes-neat", label: "Аккуратный" }, { id: "notes-slant", label: "Наклонный" }],
  paperStack: { profileId: "p", fingerprint: "v1", thicknessMm: 0.1, penDownZ: 1.4, penUpZ: 7.4 } };

beforeEach(() => {
  Object.values(mocks).forEach(m => m.mockReset());
  mocks.notesStatus.mockResolvedValue(status);
  mocks.notesPreview.mockResolvedValue({ pages: [sheet], profile: {}, warnings: [] });
  mocks.notesJobs.mockResolvedValue({ pages: [sheet], jobs: [{ number: 1, filename: "notes.gcode" }],
    profile: {}, warnings: [] });
  mocks.position.mockResolvedValue({ homed: true });
  mocks.send.mockResolvedValue({ done: true });
});
afterEach(cleanup);

function app() {
  return render(<Notes visible status={{ configured: true, online: true, job: null }}
    onAction={vi.fn()} onSetup={vi.fn()} />);
}

it("edits transcription and invalidates a previous sheet preview", async () => {
  app();
  await screen.findByText("Аккуратный");
  fireEvent.change(screen.getByLabelText("Текст конспекта"), { target: { value: "Привет" } });
  fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));
  await screen.findByText("Лист 1 из 1");
  fireEvent.change(screen.getByLabelText("Текст конспекта"), { target: { value: "Другой текст" } });
  expect(screen.queryByText("Лист 1 из 1")).toBeNull();
});

it("starts only the selected sheet after paper confirmation", async () => {
  mocks.notesPreview.mockResolvedValue({ pages: [sheet, { ...sheet, number: 2 }],
    profile: {}, warnings: [] });
  mocks.notesJobs.mockResolvedValue({ pages: [sheet, { ...sheet, number: 2 }],
    jobs: [{ number: 1, filename: "first.gcode" }, { number: 2, filename: "second.gcode" }],
    profile: {}, warnings: [] });
  app();
  await screen.findByText("Аккуратный");
  fireEvent.change(screen.getByLabelText("Текст конспекта"), { target: { value: "Привет" } });
  fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));
  await screen.findByText("Лист 1 из 2");
  fireEvent.click(screen.getByRole("button", { name: "Следующий лист" }));
  fireEvent.click(screen.getByLabelText("Ручка установлена, чистый лист закреплён"));
  fireEvent.click(screen.getByRole("button", { name: "Написать лист 2" }));
  await waitFor(() => expect(mocks.send).toHaveBeenCalledWith("second.gcode", true));
  expect(mocks.send).toHaveBeenCalledTimes(1);
  expect(mocks.notesNextSheet).not.toHaveBeenCalled();
});

it("rebuilds text pages after sheet removal and preserves the selected page", async () => {
  mocks.notesPreview.mockResolvedValue({ pages: [sheet, { ...sheet, number: 2 }], profile: {}, warnings: [] });
  mocks.notesNextSheet.mockResolvedValue({ ...status,
    paperStack: { ...status.paperStack, fingerprint: "v2", penDownZ: 1.3, penUpZ: 7.3 } });
  app();
  await screen.findByText("Аккуратный");
  fireEvent.change(screen.getByLabelText("Текст конспекта"), { target: { value: "Привет" } });
  fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));
  await screen.findByText("Лист 1 из 2");
  fireEvent.click(screen.getByRole("button", { name: "Следующий лист" }));
  fireEvent.click(screen.getByLabelText("Ручка установлена, чистый лист закреплён"));
  fireEvent.click(screen.getByRole("button", { name: "Лист убран — следующий" }));
  await screen.findByText(/Высота касания: 1,3 мм/);
  expect(mocks.notesPreview).toHaveBeenCalledTimes(2);
  expect(screen.getByText("Лист 2 из 2")).toBeTruthy();
  expect((screen.getByLabelText("Ручка установлена, чистый лист закреплён") as HTMLInputElement).checked).toBe(false);
  expect(mocks.send).not.toHaveBeenCalled();
});

it("does not offer writing before pen calibration", async () => {
  mocks.notesStatus.mockResolvedValue({ ...status, penCalibrated: false });
  app();
  await screen.findByText("Аккуратный");
  fireEvent.change(screen.getByLabelText("Текст конспекта"), { target: { value: "Привет" } });
  fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));
  await screen.findByText("Лист 1 из 1");
  fireEvent.click(screen.getByLabelText("Ручка установлена, чистый лист закреплён"));
  expect((screen.getByRole("button", { name: "Написать лист 1" }) as HTMLButtonElement).disabled).toBe(true);
});

it("requires another preview confirmation when calibration changes", async () => {
  mocks.notesJobs.mockResolvedValue({ pages: [sheet], jobs: [{ number: 1, filename: "new.gcode" }],
    profile: { id: "changed", fingerprint: "new" }, warnings: [] });
  app();
  await screen.findByText("Аккуратный");
  fireEvent.change(screen.getByLabelText("Текст конспекта"), { target: { value: "Привет" } });
  fireEvent.click(screen.getByRole("button", { name: "Предпросмотр" }));
  await screen.findByText("Лист 1 из 1");
  fireEvent.click(screen.getByLabelText("Ручка установлена, чистый лист закреплён"));
  fireEvent.click(screen.getByRole("button", { name: "Написать лист 1" }));
  await screen.findByRole("alert");
  expect(mocks.send).not.toHaveBeenCalled();
});
