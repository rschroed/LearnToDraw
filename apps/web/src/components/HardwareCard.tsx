import type { ReactNode } from "react";

import type { DeviceStatus } from "../types/hardware";
import { StatusPill } from "./StatusPill";

interface HardwareCardProps {
  title: string;
  actionLabel: string;
  status: DeviceStatus;
  onAction: () => Promise<void>;
  actionPending: boolean;
  notice?: {
    tone: "info" | "success" | "error";
    message: string;
  } | null;
  footer?: ReactNode;
  children?: ReactNode;
}

function formatDetails(details: Record<string, unknown>) {
  return Object.entries(details).filter(
    ([, value]) =>
      value !== null &&
      value !== "" &&
      (typeof value === "string" ||
        typeof value === "number" ||
        typeof value === "boolean"),
  );
}

function formatValue(value: unknown) {
  if (typeof value === "boolean") {
    return value ? "yes" : "no";
  }
  return String(value);
}

export function HardwareCard({
  title,
  actionLabel,
  status,
  onAction,
  actionPending,
  notice,
  footer,
  children,
}: HardwareCardProps) {
  const details = formatDetails(status.details);
  const actionDisabled = actionPending || status.busy || !status.available;

  return (
    <section className="hardware-card">
      <header>
        <div>
          <h2>{title}</h2>
          <div className="hardware-meta">{status.driver}</div>
        </div>
        <StatusPill
          label="Connection"
          value={status.connected ? "connected" : "disconnected"}
          tone={status.connected ? "ok" : "warn"}
        />
      </header>

      <div className="status-row">
        <StatusPill
          label="Availability"
          value={status.available ? "ready" : "offline"}
          tone={status.available ? "ok" : "warn"}
        />
        <StatusPill
          label="Activity"
          value={status.busy ? "busy" : "idle"}
          tone={status.busy ? "warn" : "ok"}
        />
      </div>

      <ul className="details-list">
        <li>
          <span>Last updated</span>
          <strong>{new Date(status.last_updated).toLocaleTimeString()}</strong>
        </li>
        {details.map(([key, value]) => (
          <li key={key}>
            <span>{key}</span>
            <strong>{formatValue(value)}</strong>
          </li>
        ))}
        {status.error ? (
          <li>
            <span>Error</span>
            <strong>{status.error}</strong>
          </li>
        ) : null}
      </ul>

      {notice ? (
        <div className={`inline-notice inline-notice-${notice.tone}`}>
          {notice.message}
        </div>
      ) : null}

      <div className="actions">
        <button
          type="button"
          className="button-primary"
          onClick={() => void onAction()}
          disabled={actionDisabled}
        >
          {actionPending ? "Working..." : actionLabel}
        </button>
      </div>

      {children}
      {footer}
    </section>
  );
}
