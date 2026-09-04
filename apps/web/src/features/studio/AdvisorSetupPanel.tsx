import { FormEvent, useEffect, useState } from "react";

import {
  clearDrawingAdvisorConfiguration,
  configureDrawingAdvisor,
  fetchDrawingAdvisorConfiguration,
} from "../../lib/api";
import type { DrawingAdvisorRuntimeStatus } from "../../types/drawing";

const DEFAULT_OPENAI_MODEL = "gpt-5.6-terra";

export function AdvisorSetupPanel() {
  const [status, setStatus] = useState<DrawingAdvisorRuntimeStatus | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(DEFAULT_OPENAI_MODEL);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void fetchDrawingAdvisorConfiguration()
      .then((nextStatus) => {
        if (controller.signal.aborted) return;
        setStatus(nextStatus);
        if (nextStatus.advisor.model) setModel(nextStatus.advisor.model);
      })
      .catch((caught: unknown) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : "Unable to load advisor setup.");
        }
      });
    return () => controller.abort();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setFeedback(null);
    try {
      const nextStatus = await configureDrawingAdvisor(apiKey, model);
      setStatus(nextStatus);
      setApiKey("");
      setFeedback(
        "OpenAI advisor loaded in backend memory. The first drawing plan will verify the key and model with OpenAI.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to configure the advisor.");
    } finally {
      setBusy(false);
    }
  }

  async function clearConfiguration() {
    setBusy(true);
    setError(null);
    setFeedback(null);
    try {
      const nextStatus = await clearDrawingAdvisorConfiguration();
      setStatus(nextStatus);
      setApiKey("");
      setModel(nextStatus.advisor.model ?? DEFAULT_OPENAI_MODEL);
      setFeedback("Runtime OpenAI configuration cleared.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to clear the advisor setup.");
    } finally {
      setBusy(false);
    }
  }

  const isRuntimeOpenAI = status?.source === "runtime";
  const statusLabel = status === null
    ? "Checking advisor…"
    : status.advisor.available
      ? `${status.advisor.driver === "openai" ? "OpenAI" : "Creative"} advisor ready`
      : "Creative advisor unavailable";

  return (
    <section className="advisor-setup" aria-labelledby="advisor-setup-title">
      <div className="advisor-setup-copy">
        <p className="eyebrow">Creative advisor</p>
        <h2 id="advisor-setup-title">Generate and assess drawings with OpenAI</h2>
        <p>
          Your key is sent only to this localhost backend and held in process memory. It is never
          saved to browser storage or LearnToDraw artifacts, and it disappears when the API stops.
        </p>
        <div className="advisor-status" aria-live="polite">
          <strong>{statusLabel}</strong>
          {status?.advisor.model ? <span>Model: {status.advisor.model}</span> : null}
          {status?.advisor.message && !status.advisor.available
            ? <span>{status.advisor.message}</span>
            : null}
        </div>
      </div>

      <form className="advisor-setup-form" onSubmit={(event) => void submit(event)}>
        <label className="field-group">
          <span>OpenAI API key</span>
          <input
            type="password"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            autoComplete="new-password"
            spellCheck={false}
            required
            disabled={busy}
            placeholder={isRuntimeOpenAI ? "Enter a replacement key" : "sk-…"}
          />
        </label>
        <label className="field-group">
          <span>Model</span>
          <input
            type="text"
            value={model}
            onChange={(event) => setModel(event.target.value)}
            autoComplete="off"
            spellCheck={false}
            required
            disabled={busy}
          />
        </label>
        <div className="advisor-setup-actions">
          <button type="submit" disabled={busy || apiKey.trim().length === 0 || model.trim().length === 0}>
            {busy ? "Saving…" : isRuntimeOpenAI ? "Replace runtime key" : "Enable OpenAI advisor"}
          </button>
          {isRuntimeOpenAI ? (
            <button type="button" className="button-secondary" disabled={busy} onClick={() => void clearConfiguration()}>
              Clear runtime key
            </button>
          ) : null}
        </div>
        {feedback ? <p className="advisor-setup-feedback" role="status">{feedback}</p> : null}
        {error ? <p className="advisor-setup-error" role="alert">{error}</p> : null}
      </form>
    </section>
  );
}
