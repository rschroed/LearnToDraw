import type { ReactNode } from "react";

import type { DeviceStatus } from "../types/hardware";
import { StatusPill } from "./StatusPill";

interface HardwareCardProps {
  title: string;
  status: DeviceStatus;
  actionLabel?: string;
  onAction?: (() => Promise<void>) | null;
  actionPending?: boolean;
  actionDisabled?: boolean;
  secondaryActionLabel?: string;
  onSecondaryAction?: (() => Promise<void>) | null;
  secondaryActionPending?: boolean;
  secondaryActionDisabled?: boolean;
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
  status,
  actionLabel,
  onAction,
  actionPending = false,
  actionDisabled,
  secondaryActionLabel,
  onSecondaryAction,
  secondaryActionPending = false,
  secondaryActionDisabled,
  notice,
  footer,
  children,
}: HardwareCardProps) {
  const details = formatDetails(status.details);
  const primaryActionDisabled =
    actionDisabled ?? (actionPending || status.busy || !status.available);
  const resolvedSecondaryActionDisabled =
    secondaryActionDisabled ??
    (secondaryActionPending || status.busy || !status.available);
  const hasPrimaryAction = Boolean(actionLabel && onAction);
  const hasSecondaryAction = Boolean(secondaryActionLabel && onSecondaryAction);

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

      {hasPrimaryAction || hasSecondaryAction ? (
        <div className="actions">
          {hasPrimaryAction ? (
            <button
              type="button"
              className="button-primary"
              onClick={() => void onAction?.()}
              disabled={primaryActionDisabled}
            >
              {actionPending ? "Working..." : actionLabel}
            </button>
          ) : null}
          {hasSecondaryAction ? (
            <button
              type="button"
              className="button-secondary"
              onClick={() => void onSecondaryAction?.()}
              disabled={resolvedSecondaryActionDisabled}
            >
              {secondaryActionPending ? "Working..." : secondaryActionLabel}
            </button>
          ) : null}
        </div>
      ) : null}

      {children}
      {footer}
    </section>
  );
}
