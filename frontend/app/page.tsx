import { BackgroundRemover } from "@/components/BackgroundRemover";

export default function Home() {
  return (
    <main>
      <header className="site-header shell">
        <a className="brand" href="#top" aria-label="FON — на главную">
          <span className="brand-mark" aria-hidden="true">F</span>
          <span>FON</span>
        </a>
        <div className="local-badge">
          <span className="status-dot" aria-hidden="true" />
          Работает локально
        </div>
      </header>

      <section className="hero shell" id="top">
        <div className="eyebrow"><SparklesIcon /> На базе BiRefNet</div>
        <h1>Фон исчезает.<br /><span>Главное остаётся.</span></h1>
        <p className="hero-copy">
          Загрузите фотографию и получите аккуратный PNG с прозрачным фоном. Без
          регистрации, облака и лишних шагов.
        </p>
      </section>

      <section className="workspace shell" aria-label="Удаление фона">
        <BackgroundRemover />
      </section>

      <section className="features shell" aria-label="Преимущества">
        <Feature icon={<LockIcon />} title="Ваши фото остаются у вас">
          Обработка выполняется локально на вашем компьютере.
        </Feature>
        <Feature icon={<ImageIcon />} title="Чистый прозрачный PNG">
          Готово для дизайна, каталога или нового фона.
        </Feature>
        <Feature icon={<BoltIcon />} title="Один понятный шаг">
          JPG, PNG и WebP размером до 15 МБ.
        </Feature>
      </section>

      <footer className="site-footer shell">
        <span>FON</span>
        <span>Локальный инструмент удаления фона</span>
      </footer>
    </main>
  );
}

function Feature({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return <article><span className="feature-icon">{icon}</span><div><h2>{title}</h2><p>{children}</p></div></article>;
}

function SparklesIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2L12 3Zm6 9 .8 2.2L21 15l-2.2.8L18 18l-.8-2.2L15 15l2.2-.8L18 12ZM6 13l1 3 3 1-3 1-1 3-1-3-3-1 3-1 1-3Z" /></svg>;
}

function LockIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10V8a5 5 0 0 1 10 0v2m-9 0h8a2 2 0 0 1 2 2v7H6v-7a2 2 0 0 1 2-2Z" /></svg>;
}

function ImageIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="9" cy="10" r="2" /><path d="m5 18 5-5 3 3 2-2 4 4" /></svg>;
}

function BoltIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m13 2-8 12h7l-1 8 8-12h-7l1-8Z" /></svg>;
}
