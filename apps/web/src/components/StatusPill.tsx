interface StatusPillProps {
  label: string;
  value: string;
  tone?: "ok" | "warn";
}

export function StatusPill({
  label,
  value,
  tone = "ok",
}: StatusPillProps) {
  return (
    <span className={`status-pill status-pill-${tone}`}>
      <span className="status-pill-dot" />
      {label}: {value}
    </span>
  );
}
