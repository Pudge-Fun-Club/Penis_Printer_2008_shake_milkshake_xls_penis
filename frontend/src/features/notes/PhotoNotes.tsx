import { useEffect, useRef, useState, type ComponentProps } from "react";
import { api } from "../../api";
import type { NotesPreview, NotesStatus } from "../../api/client/notes";
import Notes from "./Notes";
import PaperStack from "./PaperStack";

function duration(seconds: number) {
  const total = Math.round(seconds);
  return total < 60 ? `${total} с` : `${Math.floor(total / 60)} мин ${total % 60} с`;
}
const metres = (mm: number) => `${(mm / 1000).toLocaleString("ru-RU", {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
})} м`;

export default function PhotoNotes(props: ComponentProps<typeof Notes>) {
  const { visible, status, onAction, onSetup } = props;
  const [manual, setManual] = useState(false);
  const [info, setInfo] = useState<NotesStatus | null>(null);
  const [homed, setHomed] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [photoUrl, setPhotoUrl] = useState("");
  const [svgUrl, setSvgUrl] = useState("");
  const [asset, setAsset] = useState<string | null>(null);
  const [font, setFont] = useState("original");
  const [margin, setMargin] = useState(5);
  const [straighten, setStraighten] = useState(false);
  const [preview, setPreview] = useState<NotesPreview | null>(null);
  const [paperReady, setPaperReady] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [showTravel, setShowTravel] = useState(false);
  const [key, setKey] = useState("");
  const [model, setModel] = useState("gpt-4.1-mini");
  const input = useRef<HTMLInputElement>(null);
  const version = useRef(0);
  const active = /printing|paused|pausing|resuming|cancelling/i.test(status?.job?.state ?? "");
  const connected = !!status?.online;

  useEffect(() => {
    if (!visible) return;
    api.notesStatus().then(s => { setInfo(s); setModel(s.ocrModel); }).catch(e => setError(e.message));
    api.position().then(p => setHomed(p.homed)).catch(() => setHomed(false));
  }, [visible, manual, status?.online, status?.job?.state]);

  useEffect(() => {
    if (!file) { setPhotoUrl(""); return; }
    const url = URL.createObjectURL(file);
    setPhotoUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  const svg = preview?.pages[0]?.svg;
  useEffect(() => {
    if (!svg) { setSvgUrl(""); return; }
    const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
    setSvgUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [svg]);

  const invalidate = () => {
    version.current += 1;
    setPreview(null); setPaperReady(false); setError(""); setMessage("");
  };
  const choosePhoto = (photo: File) => {
    if (!/^image\/(png|jpeg|webp)$/.test(photo.type)) {
      setError("Выбери фото PNG, JPEG или WebP."); return;
    }
    if (photo.size > 15 * 1024 * 1024) { setError("Фото больше 15 МБ."); return; }
    invalidate(); setFile(photo); setAsset(null);
  };

  const build = async () => {
    if (!file) return;
    const token = version.current;
    setBusy(font === "original" ? "Превращаю страницу в SVG…" : "Выделяю текст и меняю почерк…");
    setError(""); setMessage("");
    try {
      let id = asset;
      if (!id) {
        const result = await api.notesVectorize(file, straighten, 3);
        if (token !== version.current) return;
        id = result.id; setAsset(id);
      }
      const result = await api.notesVectorPreview({ id, font, margin });
      if (token !== version.current) return;
      setPreview(result); setPaperReady(false);
      setMessage(result.warnings.join(" "));
    } catch (e) {
      if (token === version.current) setError((e as Error).message);
    } finally { setBusy(""); }
  };

  const write = async () => {
    if (!asset || !preview || !paperReady) return;
    setBusy("Готовлю G-code из SVG…"); setError(""); setMessage("");
    try {
      const result = await api.notesVectorJobs({ id: asset, font, margin });
      if (JSON.stringify({ pages: result.pages, profile: result.profile }) !==
          JSON.stringify({ pages: preview.pages, profile: preview.profile })) {
        setPreview(result); setPaperReady(false);
        throw new Error("Калибровка или SVG изменились. Проверь новый предпросмотр и подтверди бумагу ещё раз.");
      }
      const filename = result.jobs?.[0]?.filename;
      if (!filename) throw new Error("В SVG нет линий для записи.");
      await api.send(filename, true);
      setPaperReady(false); setMessage("Принтер пишет SVG. Дождись завершения перед заменой бумаги.");
      onAction();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  };

  const removeSheet = async (thickness: number) => {
    const stack = info?.paperStack;
    if (!stack || busy || active) return;
    const hadPreview = !!preview;
    invalidate();
    setBusy("Учитываю снятый лист…");
    try {
      const updated = await api.notesNextSheet({ thickness_mm: thickness,
        profile_id: stack.profileId, fingerprint: stack.fingerprint });
      setInfo(updated);
      if (asset && hadPreview) setPreview(await api.notesVectorPreview({ id: asset, font, margin }));
      setMessage("Лист учтён. Проверь SVG и снова подтверди готовность бумаги.");
      onAction();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  };

  const saveKey = async () => {
    setBusy("Сохраняю настройки…"); setError("");
    try {
      const result = await api.notesOcrSettings(key, model);
      setInfo(prev => prev ? { ...prev, ...result } : null);
      setKey(""); setShowSettings(false);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(""); }
  };
  const stop = async () => {
    try { await api.jobCommand("cancel"); onAction(); setMessage("Запись остановлена."); }
    catch (e) { setError((e as Error).message); }
  };
  const sheet = preview?.pages[0];
  const stats = sheet?.plotStats;
  const optimization = sheet?.optimization;
  const d = sheet?.polylines.map(line => "M" + line.map(([x, y]) => `${x},${y}`).join("L")).join("") ?? "";
  const travelD = sheet?.polylines.slice(1).map((line, i) => {
    const prev = sheet.polylines[i];
    return `M${prev[prev.length - 1].join(",")}L${line[0].join(",")}`;
  }).join("") ?? "";
  const ready = connected && homed && info?.penCalibrated && info?.paperCalibrated;

  if (manual) return <>
    <button onClick={() => setManual(false)}>← Фото целой страницы</button>
    <Notes {...props} />
  </>;

  return <div className="notes-view">
    <div className="notes-heading">
      <div><span className="notes-eyebrow">ПЕРЕНЕСТИ СТРАНИЦУ НА БУМАГУ</span>
        <h2>Фото → SVG → ручка</h2>
        <p>Текст, формулы, рисунки и схемы — на одном листе.</p></div>
      <button onClick={onSetup}>Настроить ручку и бумагу</button>
    </div>
    {error && <div className="banner err" role="alert">{error}</div>}
    {message && <div className="banner" role="status">{message}</div>}
    <div className="notes-columns">
      <section className="card notes-editor">
        <h3>1. Загрузить страницу</h3>
        <button className="notes-drop notes-drop-page" disabled={!!busy || active}
          onClick={() => input.current?.click()} onDragOver={e => e.preventDefault()}
          onDrop={e => { e.preventDefault(); if (!busy && !active && e.dataTransfer.files[0]) choosePhoto(e.dataTransfer.files[0]); }}>
          {photoUrl ? <img src={photoUrl} alt="Исходная страница" /> : <><span>↥</span>Перетащи фото или выбери файл<small>PNG, JPEG, WebP · до 15 МБ</small></>}
        </button>
        <input ref={input} type="file" aria-label="Фото страницы" accept="image/png,image/jpeg,image/webp" hidden
          onChange={e => { if (e.target.files?.[0]) choosePhoto(e.target.files[0]); e.target.value = ""; }} />
        <label className="notes-confirm"><input type="checkbox" checked={straighten} disabled={!!busy || active}
          onChange={e => { invalidate(); setStraighten(e.target.checked); setAsset(null); }} />Выровнять страницу по её краям</label>
        {straighten && <p className="muted">Проверь края в SVG: большая рамка рисунка может быть принята за границу листа.</p>}
        <h3>2. Почерк и размещение</h3>
        <label>Почерк<select value={font} disabled={!!busy || active} onChange={e => { invalidate(); setFont(e.target.value); }}>
          <option value="original">Как на фото</option>
          {(info?.fonts ?? []).filter(f => !["sans", "hand", "script"].includes(f.id)).map(f =>
            <option key={f.id} value={f.id}>{f.label}</option>)}
        </select></label>
        <p className="muted">«Как на фото» переводит все штрихи страницы в вектор без API-ключа. Другой почерк заменяет текстовые строки; рисунки и формулы остаются исходными.</p>
        <label>Поля, мм<input type="number" min="0" max="50" value={margin} disabled={!!busy || active}
          onChange={e => { invalidate(); setMargin(Number(e.target.value)); }} /></label>
        {font !== "original" && <>
          <p className="muted">Для выделения текстовых строк нужен API-ключ. Перед записью проверь, что замена не задела рисунки.</p>
          <button onClick={() => setShowSettings(v => !v)}>Настройки распознавания</button>
        </>}
        {showSettings && <div className="notes-ocr">
          <label>API-ключ<input type="password" autoComplete="off" value={key} onChange={e => setKey(e.target.value)} /></label>
          <label>Модель<input value={model} onChange={e => setModel(e.target.value)} /></label>
          <p className="muted">При смене почерка фото отправляется в OpenAI. «Как на фото» обрабатывается на этом компьютере.</p>
          <button disabled={!!busy || !key.trim() || !model.trim()} onClick={saveKey}>Сохранить</button>
        </div>}
        <div className="notes-actions"><button className="primary" disabled={!file || !!busy || active} onClick={build}>Сделать SVG</button>
          <button disabled={!!busy || active} onClick={() => setManual(true)}>Ввести текст вручную</button></div>
        <p className="muted">Сними страницу прямо сверху, с хорошим освещением. SVG сохранит расположение всех элементов; страница целиком уменьшится до рабочего участка бумаги.</p>
        {!!preview?.regions?.length && <details className="notes-regions"><summary>Распознанные строки ({preview.regions.length})</summary>
          {preview.regions.map((r, i) => <p key={i}>{r.text}</p>)}
        </details>}
      </section>
      <section className="card notes-output">
        <div className="notes-preview-heading"><h3>3. SVG для записи</h3>
          <span className="muted">{info ? `${info.width} × ${info.height} мм` : "…"}</span></div>
        <div className="notes-paper">
          {sheet ? <svg viewBox={`0 0 ${sheet.width} ${sheet.height}`} aria-label="Предпросмотр SVG">
            <rect width={sheet.width} height={sheet.height} fill="#fffdf6" />
            <path d={d} fill="none" stroke="#253656" strokeWidth="0.3" strokeLinecap="round" strokeLinejoin="round" />
            {showTravel && <path d={travelD} aria-label="Переходы с поднятой ручкой"
              fill="none" stroke="#c65338" strokeWidth="0.15" strokeDasharray="1 1" />}
          </svg> : <div className="notes-empty"><span>✎</span><p>Здесь появится вся страница в линиях</p><small>Загрузи фото и нажми «Сделать SVG»</small></div>}
        </div>
        {svgUrl && <a className="btn-link" href={svgUrl} download="конспект.svg">Скачать SVG</a>}
        {stats && <div className="notes-stats" aria-label="Расчёт записи SVG">
          <p>Расчётное время: <strong>≈ {duration(stats.estimatedSeconds)}</strong></p>
          {optimization && <>
            <p>Подъёмы ручки: {`${optimization.beforeStrokes} → ${stats.penLifts}`}</p>
            <p>Переходы без письма: {`${metres(optimization.beforeTravelMm)} → ${metres(optimization.afterTravelMm)}`}</p>
          </>}
          <p>Высота подъёма: {stats.penLiftMm.toLocaleString("ru-RU")} мм</p>
          <small className="muted">Оценка учитывает движения XY и Z; реальное время зависит от принтера.</small>
          {stats.penLiftMm > 5 && <p>Большая высота подъёма замедляет каждый штрих. <button onClick={onSetup}>Настроить высоту ручки</button></p>}
        </div>}
        {sheet && <label className="notes-confirm"><input type="checkbox" checked={showTravel}
          onChange={e => setShowTravel(e.target.checked)} />Показать переходы ручки</label>}
        <div className="notes-readiness">
          <span className={connected ? "notes-ok" : "notes-missing"}>{connected ? "● USB подключён" : "○ Принтер не подключён"}</span>
          <span className={info?.penCalibrated ? "notes-ok" : "notes-missing"}>{info?.penCalibrated ? "● Ручка откалибрована" : "○ Установи и откалибруй ручку"}</span>
          <span className={info?.paperCalibrated ? "notes-ok" : "notes-missing"}>{info?.paperCalibrated ? "● Бумага откалибрована" : "○ Укажи положение бумаги"}</span>
          {!homed && <span className="notes-missing">○ Сними ручку и выполни поиск нуля</span>}
        </div>
        <PaperStack info={info} disabled={!!busy || active} onRemove={removeSheet} />
        <label className="notes-confirm"><input type="checkbox" checked={paperReady} disabled={!!busy || active}
          onChange={e => setPaperReady(e.target.checked)} />Ручка установлена, чистый лист закреплён</label>
        <button className="primary notes-write" disabled={!preview || !ready || !paperReady || !!busy || active} onClick={write}>Написать SVG</button>
        {active && <div className="notes-progress"><progress max="100" value={status?.job?.progress?.completion ?? 0} /><button className="danger" onClick={stop}>Остановить запись</button></div>}
        {!!busy && <p role="status">{busy}</p>}
        {!ready && <button className="notes-actions" onClick={onSetup}>Открыть калибровку</button>}
      </section>
    </div>
  </div>;
}
