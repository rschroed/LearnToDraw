import type { ReactNode } from "react";

interface HardwareStartupStateProps {
  title: string;
  message: string;
  error?: string | null;
  children?: ReactNode;
}

export function HardwareStartupState({
  title,
  message,
  error,
  children,
}: HardwareStartupStateProps) {
  return (
    <main className="page-shell">
      <section className="hero-card">
        <h1>{title}</h1>
        <p>{message}</p>
        {children ? <div className="actions" style={{ marginTop: 16 }}>{children}</div> : null}
        {error ? <div className="banner" style={{ marginTop: 16 }}>{error}</div> : null}
      </section>
    </main>
  );
}
