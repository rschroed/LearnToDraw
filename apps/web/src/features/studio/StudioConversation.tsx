import { useEffect, useRef, useState, type FormEvent } from "react";

import type { DrawingSession, DrawingSessionEvent } from "../../types/drawing";
import type { StudioAction } from "./useStudioSession";

interface StudioConversationProps {
  session: DrawingSession;
  busyAction: StudioAction;
  onSend: (message: string) => Promise<void>;
}

function eventSpeaker(event: DrawingSessionEvent) {
  return event.type === "user_guidance" ? "You" : "Studio";
}

function eventBody(event: DrawingSessionEvent) {
  const assessment = event.details.assessment;
  if (event.type === "agent_decision" && typeof assessment === "string") {
    return `${assessment} ${event.message}`;
  }
  return event.message;
}

function formatEventTime(timestamp: string) {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function StudioConversation({
  session,
  busyAction,
  onSend,
}: StudioConversationProps) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLLIElement | null>(null);
  const canSend =
    draft.trim().length > 0 &&
    !["completed", "failed", "abandoned", "stopping"].includes(session.status) &&
    busyAction !== "message";

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [session.events.length]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSend) return;
    const message = draft.trim();
    setDraft("");
    await onSend(message);
  }

  return (
    <aside className="studio-conversation" aria-label="Drawing conversation">
      <header>
        <div>
          <p className="eyebrow">Conversation</p>
          <h2>Shape the next decision</h2>
        </div>
        {session.queued_guidance.length > 0 ? (
          <span className="studio-queued-count">
            {session.queued_guidance.length} queued
          </span>
        ) : null}
      </header>

      <ol className="studio-event-log" aria-live="polite" aria-relevant="additions text">
        {session.events.map((event) => (
          <li
            key={event.id}
            className={
              event.type === "user_guidance"
                ? "studio-event studio-event-user"
                : "studio-event studio-event-agent"
            }
          >
            <div className="studio-event-meta">
              <strong>{eventSpeaker(event)}</strong>
              <time dateTime={event.created_at}>{formatEventTime(event.created_at)}</time>
            </div>
            <p>{eventBody(event)}</p>
          </li>
        ))}
        <li ref={endRef} className="studio-event-end" aria-hidden="true" />
      </ol>

      <form className="studio-message-form" onSubmit={submit}>
        <label htmlFor="studio-guidance">
          {session.authorization.approved_at
            ? "Guidance for the next observation"
            : "Revise the plan"}
        </label>
        <textarea
          id="studio-guidance"
          value={draft}
          rows={3}
          maxLength={2000}
          disabled={["completed", "failed", "abandoned", "stopping"].includes(session.status)}
          placeholder={
            session.authorization.approved_at
              ? "For example: make the rhythm less regular"
              : "For example: leave more open space on the right"
          }
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
        />
        <div className="studio-message-actions">
          <span>⌘ Enter to send</span>
          <button type="submit" className="button-secondary" disabled={!canSend}>
            {busyAction === "message"
              ? "Sending…"
              : session.authorization.approved_at
                ? "Queue guidance"
                : "Revise plan"}
          </button>
        </div>
      </form>
    </aside>
  );
}
