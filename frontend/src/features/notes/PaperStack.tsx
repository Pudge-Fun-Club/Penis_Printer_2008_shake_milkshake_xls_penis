import { useEffect, useState } from "react";
import type { NotesStatus } from "../../api/client/notes";

export default function PaperStack({ info, disabled, onRemove }: {
  info: NotesStatus | null;
  disabled: boolean;
  onRemove: (thickness: number) => void;
}) {
  const stack = info?.paperStack;
  const [thickness, setThickness] = useState("0.1");
  useEffect(() => {
    if (stack) setThickness(String(stack.thicknessMm));
  }, [stack?.thicknessMm]);
  if (!stack) return null;
  const value = Number(thickness);
  const valid = thickness.trim() !== "" && Number.isFinite(value) && value >= 0.001 && value <= 1;
  return <div className="notes-stats notes-stack" aria-label="Стопка бумаги">
    <strong>Письмо на стопке</strong>
    <p className="muted">Откалибруй ручку на верхнем листе. Убрал один лист — нажми кнопку; общее количество знать не нужно.</p>
    <label>Толщина одного листа, мм<input type="number" min="0.001" max="1" step="0.01"
      value={thickness} disabled={disabled} onChange={e => setThickness(e.target.value)} /></label>
    <p>Высота касания: {stack.penDownZ.toLocaleString("ru-RU", { maximumFractionDigits: 3 })} мм</p>
    <button disabled={disabled || !info?.penCalibrated || !valid} onClick={() => onRemove(value)}>Лист убран — следующий</button>
    <p className="muted">Нажимай только после удаления листа: обе высоты уменьшатся на его толщину. При замене листа на той же высоте поправка не нужна.</p>
  </div>;
}
