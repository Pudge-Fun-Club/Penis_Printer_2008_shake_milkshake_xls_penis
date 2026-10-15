import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { NotesOptions, NotesPreview, NotesStatus } from "../../api/client/notes";

export default function Notes({ visible, status, onAction, onSetup }: {
  visible: boolean;
  status: { configured?: boolean; online?: boolean; job?: { state?: string; progress?: { completion?: number } } | null } | null;
  onAction: () => void;
  onSetup: () => void;
}) {
  const [info, setInfo] = useState<NotesStatus | null>(null);
  const [options, setOptions] = useState<NotesOptions>({
    text: "", font: "notes-neat", size: 4, margin: 5, line_spacing: 1.9,
  });
  const [preview, setPreview] = useState<NotesPreview | null>(null);
  const [page, setPage] = useState(0);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [paperReady, setPaperReady] = useState(false);
  const [homed, setHomed] = useState(false);
  const generation = useRef(0);
  const active = /printing|paused/i.test(status?.job?.state ?? "");
  const connected = !!status?.online;

  useEffect(() => {
    if (!visible) return;
    api.notesStatus().then(setInfo).catch(e => setError(e.message));
    api.position().then(p => setHomed(p.homed)).catch(() => setHomed(false));
  }, [visible, status?.online, status?.job?.state]);

  const change = (patch: Partial<NotesOptions>) => {
    generation.current += 1;
    setOptions(prev => ({ ...prev, ...patch }));
    setPreview(null);
    setPage(0);
    setPaperReady(false);
    setMessage("");
  };

  const buildPreview = async () => {
    const token = generation.current;
    setBusy("Готовлю листы…"); setError(""); setMessage("");
    try {
      const result = await api.notesPreview(options);
      if (token !== generation.current) return;
      setPreview(result); setPage(0); setPaperReady(false);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  };

  const write = async () => {
    if (!preview || !paperReady) return;
    setBusy("Отправляю на принтер…"); setError(""); setMessage("");
    try {
      // Generate with the current profile immediately before sending. The
      // server also checks the profile fingerprint before accepting the job.
      const ready = await api.notesJobs(options);
      if (JSON.stringify({ pages: ready.pages, profile: ready.profile }) !==
          JSON.stringify({ pages: preview.pages, profile: preview.profile })) {
        setPreview(ready); setPage(0); setPaperReady(false);
        throw new Error("Калибровка или листы изменились. Проверь новый предпросмотр и подтверди бумагу ещё раз.");
      }
      const filename = ready.jobs?.find(j => j.number === page + 1)?.filename;
      if (!filename) throw new Error("На этом листе нет текста для записи.");
      await api.send(filename, true);
      setPreview(ready); setPaperReady(false);
      setMessage(`Пишу лист ${page + 1}. Для следующего листа дождитесь завершения и замените бумагу.`);
      onAction();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  };

  const stop = async () => {
    try { await api.jobCommand("cancel"); setMessage("Запись остановлена."); onAction(); }
    catch (e) { setError((e as Error).message); }
  };
  const sheet = preview?.pages[page];
  const d = sheet?.polylines.map(line => "M" + line.map(([x, y]) => `${x},${y}`).join("L")).join("") ?? "";
  const ready = info?.penCalibrated && info?.paperCalibrated && homed && connected;

  return <div className="notes-view">
    <div className="notes-heading">
      <div><span className="notes-eyebrow">КОНСПЕКТ НА БУМАГЕ</span>
        <h2>Текст → твой почерк → бумага</h2>
        <p>Вставь текст, выбери почерк и проверь раскладку на листы.</p></div>
      <button onClick={onSetup}>Настроить ручку и бумагу</button>
    </div>
    {error && <div className="banner err" role="alert">{error}</div>}
    {message && <div className="banner" role="status">{message}</div>}
    <div className="notes-columns">
      <section className="card notes-editor">
        <h3>1. Вставь текст</h3>
        <label className="notes-text-label">Текст конспекта
          <textarea value={options.text} maxLength={20000} disabled={!!busy || active}
            onChange={e => change({ text: e.target.value })}
            placeholder="Вставь текст конспекта сюда." />
        </label>
        <small className="muted">{options.text.length} / 20 000 символов · проверь числа и формулы</small>
        <h3>2. Выбери почерк</h3>
        <label>Почерк<select value={options.font} disabled={!!busy || active} onChange={e => change({ font: e.target.value })}>
          {(info?.fonts ?? []).map(f => <option key={f.id} value={f.id}>{f.label}</option>)}
        </select></label>
        <p className="muted">Три русских почерка включены. Свой можно записать в редакторе шрифтов.</p>
        <div className="notes-fields">
          <label>Высота букв, мм<input type="number" min="1.5" max="15" step="0.5" value={options.size}
            disabled={!!busy || active} onChange={e => change({ size: Number(e.target.value) })} /></label>
          <label>Поля, мм<input type="number" min="0" max="50" step="1" value={options.margin}
            disabled={!!busy || active} onChange={e => change({ margin: Number(e.target.value) })} /></label>
          <label>Интервал строк<input type="number" min="1.5" max="4" step="0.1" value={options.line_spacing}
            disabled={!!busy || active} onChange={e => change({ line_spacing: Number(e.target.value) })} /></label>
        </div>
        <button className="primary" disabled={!options.text.trim() || !!busy || active} onClick={buildPreview}>Предпросмотр</button>
      </section>
      <section className="card notes-output">
        <div className="notes-preview-heading"><h3>Так будет на бумаге</h3>
          <span className="muted">{info ? `${info.width} × ${info.height} мм` : "…"}</span></div>
        <div className="notes-paper">
          {sheet ? <svg viewBox={`0 0 ${sheet.width} ${sheet.height}`} aria-label="Предпросмотр листа">
            <rect width={sheet.width} height={sheet.height} fill="#fffdf6" />
            <path d={d} fill="none" stroke="#253656" strokeWidth="0.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg> : <div className="notes-empty"><span>✎</span><p>Здесь появится настоящий путь ручки</p><small>Добавь текст и нажми «Предпросмотр»</small></div>}
        </div>
        {preview && <div className="notes-pagination">
          <button aria-label="Предыдущий лист" disabled={page === 0 || !!busy || active} onClick={() => { setPage(p => p - 1); setPaperReady(false); }}>←</button>
          <strong>Лист {page + 1} из {preview.pages.length}</strong>
          <button aria-label="Следующий лист" disabled={page + 1 >= preview.pages.length || !!busy || active} onClick={() => { setPage(p => p + 1); setPaperReady(false); }}>→</button>
        </div>}
        <div className="notes-readiness">
          <span className={connected ? "notes-ok" : "notes-missing"}>{connected ? "● USB подключён" : "○ Принтер не подключён"}</span>
          <span className={info?.penCalibrated ? "notes-ok" : "notes-missing"}>{info?.penCalibrated ? "● Ручка откалибрована" : "○ Установи и откалибруй ручку"}</span>
          <span className={info?.paperCalibrated ? "notes-ok" : "notes-missing"}>{info?.paperCalibrated ? "● Бумага откалибрована" : "○ Укажи положение бумаги"}</span>
          {!homed && <span className="notes-missing">○ Сними ручку и выполни поиск нуля</span>}
        </div>
        <label className="notes-confirm"><input type="checkbox" checked={paperReady}
          disabled={!!busy || active} onChange={e => setPaperReady(e.target.checked)} />Ручка установлена, чистый лист закреплён</label>
        <button className="primary notes-write" disabled={!sheet?.polylines.length || !ready || !paperReady || !!busy || active} onClick={write}>Написать лист {page + 1}</button>
        {active && <div className="notes-progress"><progress max="100" value={status?.job?.progress?.completion ?? 0} />
          <button className="danger" onClick={stop}>Остановить запись</button></div>}
        <p className="muted">Каждый лист запускается отдельно после замены бумаги. Для страницы с рисунками вернись в режим фото → SVG.</p>
        {busy && <p role="status">{busy}</p>}
        {!ready && <button onClick={onSetup}>Открыть калибровку</button>}
      </section>
    </div>
  </div>;
}
