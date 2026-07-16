"use client";

import type { CSSProperties, ChangeEvent, DragEvent, KeyboardEvent } from "react";
import { useEffect, useRef, useState } from "react";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL
  ?? (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : "")
).replace(/\/$/, "");
const UPLOAD_MODE = process.env.NEXT_PUBLIC_UPLOAD_MODE ?? "direct";
const configuredMaxSize = Number(process.env.NEXT_PUBLIC_MAX_FILE_SIZE_MB ?? "15");
const MAX_FILE_SIZE_MB = Number.isFinite(configuredMaxSize) ? configuredMaxSize : 15;
const MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024;
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

type SelectedImage = {
  file: File;
  url: string;
  width: number;
  height: number;
};

type PresignedUpload = {
  objectKey: string;
  uploadUrl: string;
  uploadHeaders: Record<string, string>;
};

type BackgroundRemovalJob = {
  id: string;
  status: string;
  resultUrl: string | null;
  error: string | null;
};

export function BackgroundRemover() {
  const inputRef = useRef<HTMLInputElement>(null);
  const objectUrls = useRef(new Set<string>());
  const [selected, setSelected] = useState<SelectedImage | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const urls = objectUrls.current;
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  function clearObjectUrls() {
    objectUrls.current.forEach((url) => URL.revokeObjectURL(url));
    objectUrls.current.clear();
  }

  function reset() {
    clearObjectUrls();
    setSelected(null);
    setResultUrl(null);
    setError(null);
    setIsDragging(false);
    if (inputRef.current) inputRef.current.value = "";
  }

  async function chooseFile(file: File | undefined) {
    setError(null);
    if (!file) return;
    if (!ACCEPTED_TYPES.has(file.type)) {
      setError("Выберите изображение в формате JPG, PNG или WebP.");
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setError(`Файл слишком большой. Максимальный размер — ${MAX_FILE_SIZE_MB} МБ.`);
      return;
    }

    clearObjectUrls();
    setSelected(null);
    setResultUrl(null);
    const url = URL.createObjectURL(file);
    objectUrls.current.add(url);

    try {
      const dimensions = await getImageDimensions(url);
      setSelected({ file, url, ...dimensions });
    } catch {
      URL.revokeObjectURL(url);
      objectUrls.current.delete(url);
      setError("Браузер не смог прочитать это изображение.");
    }
  }

  function onFileInput(event: ChangeEvent<HTMLInputElement>) {
    void chooseFile(event.target.files?.[0]);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    void chooseFile(event.dataTransfer.files?.[0]);
  }

  function onDropzoneKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      inputRef.current?.click();
    }
  }

  async function processImage() {
    if (!selected || isProcessing) return;
    setError(null);
    setIsProcessing(true);

    try {
      if (!API_URL) {
        throw new Error("Адрес production API не задан. Укажите NEXT_PUBLIC_API_URL при сборке.");
      }

      if (UPLOAD_MODE === "storage") {
        setResultUrl(await processThroughObjectStorage(selected.file));
      } else {
        const body = new FormData();
        body.append("file", selected.file);
        const response = await fetch(`${API_URL}/api/remove-background`, {
          method: "POST",
          body,
        });
        if (!response.ok) {
          throw new Error(await getApiError(response));
        }
        if (!response.headers.get("content-type")?.includes("image/png")) {
          throw new Error("Сервер вернул неожиданный формат результата.");
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        objectUrls.current.add(url);
        setResultUrl(url);
      }
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Не удалось обработать изображение.";
      if (cause instanceof TypeError) {
        setError("Не удалось соединиться с API или object storage. Проверьте public URL и CORS.");
      } else {
        setError(message);
      }
    } finally {
      setIsProcessing(false);
    }
  }

  async function processThroughObjectStorage(file: File): Promise<string> {
    const presignResponse = await fetch(`${API_URL}/api/uploads/presign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, contentType: file.type }),
    });
    if (!presignResponse.ok) {
      throw new Error(await getApiError(presignResponse));
    }
    const presigned = (await presignResponse.json()) as PresignedUpload;

    const uploadResponse = await fetch(presigned.uploadUrl, {
      method: "PUT",
      headers: presigned.uploadHeaders,
      body: file,
    });
    if (!uploadResponse.ok) {
      throw new Error("Не удалось загрузить исходное изображение в object storage.");
    }

    const jobResponse = await fetch(`${API_URL}/api/remove-background/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objectKey: presigned.objectKey }),
    });
    if (!jobResponse.ok) {
      throw new Error(await getApiError(jobResponse));
    }
    const job = (await jobResponse.json()) as BackgroundRemovalJob;
    if (job.status !== "completed" || !job.resultUrl) {
      throw new Error(job.error || "Обработка изображения не завершилась.");
    }
    return job.resultUrl;
  }

  function downloadResult() {
    if (!resultUrl || !selected) return;
    const baseName = selected.file.name.replace(/\.[^.]+$/, "") || "image";
    const anchor = document.createElement("a");
    anchor.href = resultUrl;
    anchor.download = `${baseName}-no-bg.png`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }

  return (
    <div className="remover-card">
      {!selected ? (
        <div
          className={`dropzone ${isDragging ? "is-dragging" : ""}`}
          data-testid="upload-dropzone"
          role="button"
          tabIndex={0}
          aria-label="Выбрать изображение"
          onClick={() => inputRef.current?.click()}
          onKeyDown={onDropzoneKeyDown}
          onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node)) setIsDragging(false);
          }}
          onDrop={onDrop}
        >
          <input
            ref={inputRef}
            className="visually-hidden"
            type="file"
            accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
            onChange={onFileInput}
          />
          <span className="upload-visual" aria-hidden="true"><UploadIcon /></span>
          <div>
            <h2>{isDragging ? "Отпустите фотографию" : "Перетащите фотографию сюда"}</h2>
            <p>или нажмите, чтобы выбрать файл</p>
          </div>
          <span className="format-note">JPG, PNG, WebP · до {MAX_FILE_SIZE_MB} МБ</span>
        </div>
      ) : resultUrl ? (
        <ResultView
          original={selected}
          resultUrl={resultUrl}
          onDownload={downloadResult}
          onReset={reset}
        />
      ) : (
        <PreviewView
          selected={selected}
          isProcessing={isProcessing}
          onProcess={() => void processImage()}
          onReset={reset}
        />
      )}

      {error && <div className="error-message" role="alert"><AlertIcon /> <span>{error}</span></div>}
    </div>
  );
}

function PreviewView({ selected, isProcessing, onProcess, onReset }: {
  selected: SelectedImage;
  isProcessing: boolean;
  onProcess: () => void;
  onReset: () => void;
}) {
  return (
    <div className="preview-layout">
      <div className="preview-image-wrap" data-testid="image-preview">
        <img src={selected.url} alt="Предпросмотр выбранной фотографии" draggable={false} />
        {isProcessing && (
          <div className="processing-overlay" aria-live="polite">
            <span className="spinner" aria-hidden="true" />
            <strong>Модель отделяет объект от фона</strong>
            <span>Обработка может занять немного времени</span>
          </div>
        )}
      </div>
      <div className="preview-sidebar">
        <div>
          <span className="section-kicker">Исходник</span>
          <h2>Фотография готова</h2>
          <p className="file-name" title={selected.file.name}>{selected.file.name}</p>
          <p className="file-meta">{formatFileSize(selected.file.size)} · {selected.width} × {selected.height}</p>
        </div>
        <div className="action-stack">
          <button className="button button-primary" data-testid="remove-background" type="button" onClick={onProcess} disabled={isProcessing}>
            {isProcessing ? <><span className="button-spinner" /> Удаляем фон…</> : <><WandIcon /> Удалить фон</>}
          </button>
          <button className="button button-ghost" type="button" onClick={onReset} disabled={isProcessing}>Выбрать другое фото</button>
        </div>
      </div>
    </div>
  );
}

function ResultView({ original, resultUrl, onDownload, onReset }: {
  original: SelectedImage;
  resultUrl: string;
  onDownload: () => void;
  onReset: () => void;
}) {
  return (
    <div className="result-layout">
      <div className="result-heading">
        <div><span className="success-pill"><CheckIcon /> Готово</span><h2>Фон удалён</h2></div>
        <p>Перетащите ползунок, чтобы сравнить результат.</p>
      </div>
      <ComparisonSlider originalUrl={original.url} resultUrl={resultUrl} />
      <div className="result-actions">
        <button className="button button-secondary" type="button" onClick={onReset}><RefreshIcon /> Другое фото</button>
        <button className="button button-primary" type="button" onClick={onDownload}><DownloadIcon /> Скачать PNG</button>
      </div>
    </div>
  );
}

function ComparisonSlider({ originalUrl, resultUrl }: {
  originalUrl: string;
  resultUrl: string;
}) {
  const [split, setSplit] = useState(50);
  const style = { "--split": `${split}%` } as CSSProperties;

  return (
    <div className="comparison" style={style}>
      <img className="comparison-original" src={originalUrl} alt="Фотография до удаления фона" />
      <div className="comparison-result" aria-hidden="true"><img src={resultUrl} alt="" /></div>
      <span className="comparison-label label-before">До</span>
      <span className="comparison-label label-after">После</span>
      <div className="comparison-divider" aria-hidden="true"><span><CompareIcon /></span></div>
      <input
        className="comparison-range"
        type="range"
        min="0"
        max="100"
        value={split}
        aria-label="Сравнение до и после"
        onChange={(event) => setSplit(Number(event.target.value))}
      />
    </div>
  );
}

function getImageDimensions(url: string): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve({ width: image.naturalWidth, height: image.naturalHeight });
    image.onerror = reject;
    image.src = url;
  });
}

async function getApiError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail || `Ошибка сервера (${response.status}).`;
  } catch {
    return `Ошибка сервера (${response.status}).`;
  }
}

function formatFileSize(bytes: number) {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
    : `${Math.max(1, Math.round(bytes / 1024))} КБ`;
}

function UploadIcon() { return <svg viewBox="0 0 24 24"><path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M5 14v5h14v-5" /></svg>; }
function WandIcon() { return <svg viewBox="0 0 24 24"><path d="m4 20 11-11m-8-2 2 2m6-6 .7 2.3L18 6l-2.3.7L15 9l-.7-2.3L12 6l2.3-.7L15 3Zm4 9 .6 1.8 1.9.7-1.9.6L19 18l-.6-1.9-1.9-.6 1.9-.7L19 12Z" /></svg>; }
function DownloadIcon() { return <svg viewBox="0 0 24 24"><path d="M12 3v12m0 0 4-4m-4 4-4-4M5 19h14" /></svg>; }
function RefreshIcon() { return <svg viewBox="0 0 24 24"><path d="M4 12a8 8 0 0 1 13.7-5.6L20 9m0-5v5h-5m5 3a8 8 0 0 1-13.7 5.6L4 15m0 5v-5h5" /></svg>; }
function CheckIcon() { return <svg viewBox="0 0 24 24"><path d="m6 12 4 4 8-9" /></svg>; }
function AlertIcon() { return <svg viewBox="0 0 24 24"><path d="M12 8v5m0 3h.01M10.3 4.8 3.2 17.1A2 2 0 0 0 5 20h14a2 2 0 0 0 1.8-2.9L13.7 4.8a2 2 0 0 0-3.4 0Z" /></svg>; }
function CompareIcon() { return <svg viewBox="0 0 24 24"><path d="m9 8-4 4 4 4m6-8 4 4-4 4" /></svg>; }
