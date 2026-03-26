import { useEffect, useMemo, useState, type ChangeEvent } from "react";

import { fetchPlotRun } from "../../lib/api";
import type { CaptureMetadata, HardwareStatus, PlotterWorkspace } from "../../types/hardware";
import type { PlotAsset, PlotRun, PlotRunSummary } from "../../types/plotting";
import {
  formatPhysicalSize,
  formatResultMeta,
  formatRunMetaStrip,
  formatShortTimestamp,
  getRunStatusTone,
  getStageLabel,
  getStepSummaryItems,
  getStepSummaryNote,
  isRecord,
} from "./plotWorkflowFormatters";
import type { PlotWorkflowController } from "./usePlotWorkflow";

type PlotWorkflowMode = "workflow" | "history";

interface PlotWorkflowPanelProps {
  controller: PlotWorkflowController;
  hardwareStatus: HardwareStatus;
  plotterWorkspace: PlotterWorkspace | null;
  latestCapture: CaptureMetadata | null;
  mode?: PlotWorkflowMode;
}

interface RunDetailRow {
  label: string;
  value: string;
}

function resolvePreparedArtifactUrl(publicUrl: string) {
  if (/^https?:\/\//.test(publicUrl)) {
    return publicUrl;
  }
  if (typeof window === "undefined") {
    return publicUrl;
  }
  const { protocol, hostname, port } = window.location;
  if ((hostname === "127.0.0.1" || hostname === "localhost") && port !== "8000") {
    return `${protocol}//${hostname}:8000${publicUrl}`;
  }
  return publicUrl;
}

function getWorkflowBlockerMessage({
  selectedAsset,
  hardwareStatus,
  plotterWorkspace,
  busyAction,
  activeRun,
}: {
  selectedAsset: PlotWorkflowController["selectedAsset"];
  hardwareStatus: HardwareStatus;
  plotterWorkspace: PlotterWorkspace | null;
  busyAction: PlotWorkflowController["busyAction"];
  activeRun: boolean;
}) {
  if (activeRun) {
    return "A run is already in progress. Wait for it to finish before starting another.";
  }
  if (!selectedAsset) {
    return "Stage an SVG or load the test grid to begin a plot run.";
  }
  if (plotterWorkspace?.is_valid === false) {
    return `Paper setup needs attention before plotting: ${
      plotterWorkspace.validation_error ??
      "saved paper setup no longer fits the current machine bounds."
    }`;
  }
  if (!hardwareStatus.plotter.available) {
    return "The plotter is not ready. Review the Machine tab and restore plotter availability.";
  }
  if (!hardwareStatus.camera.available) {
    return "The camera is not ready. Review the Machine tab and restore camera readiness before running the loop.";
  }
  if (hardwareStatus.plotter.busy || hardwareStatus.camera.busy || busyAction === "start") {
    return "A machine action is still in progress. Wait for the hardware to return to idle.";
  }
  return null;
}

function formatRunKindLabel(kind: PlotAsset["kind"]) {
  return kind === "built_in_pattern" ? "Built-in pattern" : "Uploaded SVG";
}

function getHistoryRowThumbnail(run: PlotRun | null) {
  if (!run) {
    return null;
  }
  const resultCapture = run.observed_result?.capture ?? run.capture ?? null;
  if (resultCapture) {
    return {
      url: resultCapture.public_url,
      alt: `Result preview for ${run.asset.name}`,
      label: "result",
    };
  }
  if (run.prepared_artifact) {
    return {
      url: resolvePreparedArtifactUrl(run.prepared_artifact.public_url),
      alt: `Prepared preview for ${run.asset.name}`,
      label: "prepared",
    };
  }
  return {
    url: run.asset.public_url,
    alt: `Source preview for ${run.asset.name}`,
    label: "source",
  };
}

function getStatusLabel(status: PlotRun["status"]) {
  if (status === "completed") {
    return "Completed";
  }
  if (status === "failed") {
    return "Failed";
  }
  if (status === "capturing") {
    return "Capturing";
  }
  if (status === "plotting") {
    return "Plotting";
  }
  return "Preparing";
}

function getPreparationDetails(run: PlotRun | null) {
  const preparation =
    run && isRecord(run.plotter_run_details.preparation)
      ? run.plotter_run_details.preparation
      : null;
  const sourceSize = preparation
    ? formatPhysicalSize(preparation.source_width, preparation.source_height)
    : null;
  const preparedSize = preparation
    ? formatPhysicalSize(preparation.prepared_width_mm, preparation.prepared_height_mm)
    : null;
  const pageSize = preparation
    ? formatPhysicalSize(preparation.page_width_mm, preparation.page_height_mm)
    : null;
  const drawableArea = preparation
    ? formatPhysicalSize(preparation.drawable_width_mm, preparation.drawable_height_mm)
    : null;

  return [
    sourceSize ? { label: "Source size", value: sourceSize } : null,
    preparedSize ? { label: "Prepared size", value: preparedSize } : null,
    pageSize ? { label: "Page size", value: pageSize } : null,
    drawableArea ? { label: "Drawable area", value: drawableArea } : null,
  ].filter((detail): detail is RunDetailRow => detail !== null);
}

function getCollapsedRowMeta(summary: PlotRunSummary, includeTimestamp: boolean) {
  const tokens = [formatRunKindLabel(summary.asset_kind)];
  if (summary.purpose !== "normal") {
    tokens.push(summary.purpose);
  }
  if (includeTimestamp) {
    tokens.push(formatShortTimestamp(summary.created_at));
  }
  return tokens.filter(Boolean).join(" · ");
}

function getExpandedMeta(run: PlotRun | PlotRunSummary, kindLabel: string) {
  return formatRunMetaStrip({
    kindLabel,
    run,
  });
}

function getResultFooter({
  capture,
  run,
}: {
  capture: CaptureMetadata | null;
  run: PlotRun | null;
}) {
  if (capture) {
    return formatResultMeta({ capture, includeTimestamp: false });
  }
  if (run?.capture_mode === "skip") {
    return "Capture skipped";
  }
  if (run?.status === "failed") {
    return run.error ?? "No result saved";
  }
  return null;
}

function ArtifactCard({
  className,
  title,
  imageUrl,
  alt,
  emptyMessage,
  footer,
}: {
  className?: string;
  title: string;
  imageUrl?: string | null;
  alt?: string;
  emptyMessage: string;
  footer?: string | null;
}) {
  return (
    <article className={className ? `artifact-card ${className}` : "artifact-card"}>
      <header className="artifact-card-header">
        <h3>{title}</h3>
      </header>
      <div className="artifact-frame">
        {imageUrl ? (
          <img src={imageUrl} alt={alt ?? title} />
        ) : (
          <div className="empty-state">{emptyMessage}</div>
        )}
      </div>
      {footer ? <p className="artifact-footer">{footer}</p> : null}
    </article>
  );
}

function RunHeader({
  title,
  status,
  tone,
  meta,
}: {
  title: string;
  status: string;
  tone: ReturnType<typeof getRunStatusTone>;
  meta: string;
}) {
  return (
    <header className="run-header">
      <div className="run-header-main">
        <h3>{title}</h3>
        <span className={`status-pill status-pill-${tone}`}>
          <span className="status-pill-dot" />
          {status}
        </span>
      </div>
      <p className="run-meta-strip">{meta}</p>
    </header>
  );
}

function RunStepSummary({ run }: { run: PlotRun | null }) {
  const items = getStepSummaryItems(run);
  const note = getStepSummaryNote(run);

  if (!run || items.length === 0) {
    return null;
  }

  return (
    <section className="run-step-summary">
      <div className="run-step-strip">
        {items.map((item) => (
          <span key={item.key} className={`run-step-pill run-step-pill-${item.tone}`}>
            {item.label}
          </span>
        ))}
      </div>
      {note ? <p className="run-step-note">{note}</p> : null}
    </section>
  );
}

function RunDetailsBlock({ rows }: { rows: RunDetailRow[] }) {
  if (rows.length === 0) {
    return null;
  }

  return (
    <section className="run-details-block">
      <h4>Details</h4>
      <dl className="run-details-grid">
        {rows.map((row) => (
          <div key={row.label} className="run-details-row">
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function RunSourceInspect({
  asset,
  open,
  onToggle,
}: {
  asset: PlotAsset | null;
  open: boolean;
  onToggle: () => void;
}) {
  if (!asset) {
    return null;
  }

  return (
    <section className="run-source-section">
      <button type="button" className="button-ghost source-inspect-toggle" onClick={onToggle}>
        {open ? "Hide source" : "View source"}
      </button>

      {open ? (
        <div className="source-inspect-drawer">
          <ArtifactCard
            title="Source"
            imageUrl={asset.public_url}
            alt={`Source reference ${asset.name}`}
            emptyMessage="Source preview unavailable."
            footer={asset.name}
          />
        </div>
      ) : null}
    </section>
  );
}

function RunArtifactCompare({
  preparedImageUrl,
  preparedAlt,
  preparedFooter,
  resultImageUrl,
  resultAlt,
  resultFooter,
  preparedEmptyMessage,
  resultEmptyMessage,
}: {
  preparedImageUrl: string | null;
  preparedAlt: string;
  preparedFooter: string | null;
  resultImageUrl: string | null;
  resultAlt: string;
  resultFooter: string | null;
  preparedEmptyMessage: string;
  resultEmptyMessage: string;
}) {
  return (
    <div className="run-artifact-compare">
      <ArtifactCard
        className="artifact-card-prepared"
        title="Prepared"
        imageUrl={preparedImageUrl}
        alt={preparedAlt}
        emptyMessage={preparedEmptyMessage}
        footer={preparedFooter}
      />
      <ArtifactCard
        className="artifact-card-result"
        title="Result"
        imageUrl={resultImageUrl}
        alt={resultAlt}
        emptyMessage={resultEmptyMessage}
        footer={resultFooter}
      />
    </div>
  );
}

function ExpandedRunSummary({
  title,
  meta,
  status,
  statusTone,
  run,
  preparedImageUrl,
  resultCapture,
  sourceAsset,
  sourceInspectOpen,
  onToggleSource,
}: {
  title: string;
  meta: string;
  status: string;
  statusTone: ReturnType<typeof getRunStatusTone>;
  run: PlotRun | null;
  preparedImageUrl: string | null;
  resultCapture: CaptureMetadata | null;
  sourceAsset: PlotAsset | null;
  sourceInspectOpen: boolean;
  onToggleSource: () => void;
}) {
  const detailRows = getPreparationDetails(run);

  return (
    <section className="run-summary-card">
      <RunHeader title={title} status={status} tone={statusTone} meta={meta} />

      <RunArtifactCompare
        preparedImageUrl={preparedImageUrl}
        preparedAlt={run ? `Prepared output for run ${run.id}` : "Prepared output"}
        preparedFooter={sourceAsset?.name ?? null}
        resultImageUrl={resultCapture?.public_url ?? null}
        resultAlt={run ? `Result image for run ${run.id}` : "Result image"}
        resultFooter={getResultFooter({ capture: resultCapture, run })}
        preparedEmptyMessage={
          run ? "Prepared output unavailable." : "Prepared output appears after a run is prepared."
        }
        resultEmptyMessage={
          run
            ? run.capture_mode === "skip"
              ? "Capture skipped for this run."
              : run.status === "failed"
                ? run.error ?? "No result saved."
                : "Result appears once the run reaches capture."
            : "No saved result yet."
        }
      />

      <RunStepSummary run={run} />
      <RunDetailsBlock rows={detailRows} />
      <RunSourceInspect asset={sourceAsset} open={sourceInspectOpen} onToggle={onToggleSource} />
    </section>
  );
}

function WorkflowRunSummary({
  displayRun,
  selectedAsset,
  latestCapture,
  sourceOpen,
  onToggleSource,
}: {
  displayRun: PlotRun | null;
  selectedAsset: PlotAsset | null;
  latestCapture: CaptureMetadata | null;
  sourceOpen: boolean;
  onToggleSource: () => void;
}) {
  const sourceAsset = displayRun?.asset ?? selectedAsset;
  const resultCapture = displayRun?.observed_result?.capture ?? displayRun?.capture ?? latestCapture;
  const preparedImageUrl = displayRun?.prepared_artifact
    ? resolvePreparedArtifactUrl(displayRun.prepared_artifact.public_url)
    : null;

  return (
    <section className="panel comparison-panel">
      <header className="comparison-header">
        <div>
          <p className="eyebrow">Workflow</p>
          {displayRun ? (
            <p className="run-meta-strip comparison-meta">
              {getExpandedMeta(displayRun, formatRunKindLabel(displayRun.asset.kind))}
            </p>
          ) : latestCapture ? (
            <p className="run-meta-strip comparison-meta">Latest saved result</p>
          ) : null}
        </div>
        <div className="comparison-header-actions">
          <span className={`status-pill status-pill-${getRunStatusTone(displayRun?.status ?? "idle")}`}>
            <span className="status-pill-dot" />
            {displayRun ? getStageLabel(displayRun) : latestCapture ? "Result ready" : "Idle"}
          </span>
        </div>
      </header>

      <RunArtifactCompare
        preparedImageUrl={preparedImageUrl}
        preparedAlt={displayRun ? `Prepared output for run ${displayRun.id}` : "Prepared output"}
        preparedFooter={sourceAsset?.name ?? null}
        resultImageUrl={resultCapture?.public_url ?? null}
        resultAlt={
          displayRun && resultCapture
            ? `Result image for run ${displayRun.id}`
            : latestCapture
              ? `Latest result capture ${latestCapture.id}`
              : "Result image"
        }
        resultFooter={
          displayRun
            ? getResultFooter({
                capture: displayRun.observed_result?.capture ?? displayRun.capture ?? null,
                run: displayRun,
              })
            : latestCapture
              ? formatResultMeta({ capture: latestCapture, includeTimestamp: false })
              : null
        }
        preparedEmptyMessage={
          displayRun
            ? "Prepared output unavailable."
            : "Prepared output appears after a run is prepared."
        }
        resultEmptyMessage={
          displayRun
            ? displayRun.capture_mode === "skip"
              ? "Capture skipped for this run."
              : displayRun.status === "failed"
                ? displayRun.error ?? "No result saved."
                : "Result appears once the run reaches capture."
            : "No saved result yet."
        }
      />

      <RunStepSummary run={displayRun} />
      <RunDetailsBlock rows={getPreparationDetails(displayRun)} />
      <RunSourceInspect asset={sourceAsset} open={sourceOpen} onToggle={onToggleSource} />
    </section>
  );
}

export function PlotWorkflowPanel({
  controller,
  hardwareStatus,
  plotterWorkspace,
  latestCapture,
  mode = "workflow",
}: PlotWorkflowPanelProps) {
  const {
    selectedAsset,
    selectionSource,
    latestRun,
    inspectedRun,
    inspectedRunId,
    recentRuns,
    busyAction,
    activeRun,
    error,
    notice,
    createBuiltInPattern,
    uploadSvg,
    startRun,
    inspectRun,
  } = controller;
  const [historyRunDetails, setHistoryRunDetails] = useState<Record<string, PlotRun>>({});
  const [workflowSourceOpen, setWorkflowSourceOpen] = useState(false);
  const [historySourceInspectId, setHistorySourceInspectId] = useState<string | null>(null);
  const displayRun = inspectedRun;
  const workspaceInvalidReason =
    plotterWorkspace?.is_valid === false
      ? plotterWorkspace.validation_error ??
        "Saved paper setup no longer fits the current plotter bounds."
      : null;
  const startDisabled =
    !selectedAsset ||
    activeRun ||
    busyAction === "start" ||
    workspaceInvalidReason !== null ||
    !hardwareStatus.plotter.available ||
    !hardwareStatus.camera.available ||
    hardwareStatus.plotter.busy ||
    hardwareStatus.camera.busy;
  const latestRunUsesDifferentSource =
    selectionSource === "manual" &&
    selectedAsset !== null &&
    latestRun !== null &&
    latestRun.asset.id !== selectedAsset.id;
  const blockerMessage = getWorkflowBlockerMessage({
    selectedAsset,
    hardwareStatus,
    plotterWorkspace,
    busyAction,
    activeRun,
  });
  const workflowStatus = blockerMessage
    ? { tone: "warn" as const, message: blockerMessage }
    : notice
      ? { tone: notice.tone, message: notice.message }
      : selectedAsset
        ? { tone: "success" as const, message: "Ready to start a plot run." }
        : { tone: "info" as const, message: "Stage a source to begin the plotter/camera loop." };

  useEffect(() => {
    if (latestRun) {
      setHistoryRunDetails((current) =>
        current[latestRun.id] === latestRun ? current : { ...current, [latestRun.id]: latestRun },
      );
    }
  }, [latestRun]);

  useEffect(() => {
    if (inspectedRun) {
      setHistoryRunDetails((current) =>
        current[inspectedRun.id] === inspectedRun
          ? current
          : { ...current, [inspectedRun.id]: inspectedRun },
      );
    }
  }, [inspectedRun]);

  useEffect(() => {
    setWorkflowSourceOpen(false);
  }, [displayRun?.id, selectedAsset?.id]);

  useEffect(() => {
    setHistorySourceInspectId(null);
  }, [inspectedRunId]);

  useEffect(() => {
    if (mode !== "history" || recentRuns.length === 0) {
      return;
    }

    const missingRunIds = recentRuns
      .map((run) => run.id)
      .filter((runId) => historyRunDetails[runId] === undefined);
    if (missingRunIds.length === 0) {
      return;
    }

    let cancelled = false;
    void Promise.all(
      missingRunIds.map(async (runId) => {
        try {
          const run = await fetchPlotRun(runId);
          if (cancelled) {
            return null;
          }
          return run;
        } catch {
          return null;
        }
      }),
    ).then((runs) => {
      if (cancelled) {
        return;
      }
      setHistoryRunDetails((current) => {
        const next = { ...current };
        for (const run of runs) {
          if (run) {
            next[run.id] = run;
          }
        }
        return next;
      });
    });

    return () => {
      cancelled = true;
    };
  }, [historyRunDetails, mode, recentRuns]);

  const historyRows = useMemo(
    () =>
      recentRuns.map((run) => ({
        summary: run,
        detail:
          historyRunDetails[run.id] ??
          (latestRun?.id === run.id ? latestRun : null) ??
          (inspectedRun?.id === run.id ? inspectedRun : null),
        selected: inspectedRunId === run.id,
      })),
    [historyRunDetails, inspectedRun, inspectedRunId, latestRun, recentRuns],
  );

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      void uploadSvg(file);
      event.target.value = "";
    }
  }

  if (mode === "history") {
    return (
      <section className="panel history-list-panel">
        <header className="section-heading">
          <div>
            <p className="eyebrow">History</p>
            <h2>Recent runs</h2>
          </div>
        </header>
        {error ? <div className="banner">{error}</div> : null}
        {historyRows.length === 0 ? (
          <div className="empty-state">No plot runs yet.</div>
        ) : (
          <div className="history-row-list">
            {historyRows.map(({ summary, detail, selected }) => {
              const thumbnail = getHistoryRowThumbnail(detail);
              const resultCapture = detail?.observed_result?.capture ?? detail?.capture ?? null;
              const sourceInspectOpen = historySourceInspectId === summary.id;
              const title = detail?.asset.name ?? summary.asset_name;
              const meta = getExpandedMeta(detail ?? summary, formatRunKindLabel(summary.asset_kind));

              return (
                <article
                  key={summary.id}
                  className={`history-row${selected ? " history-row-selected" : ""}`}
                >
                  <button
                    type="button"
                    className="history-row-summary"
                    onClick={() => void inspectRun(summary.id)}
                  >
                    <div className="history-row-thumb">
                      {thumbnail ? (
                        <>
                          <img src={thumbnail.url} alt={thumbnail.alt} />
                          <span className="history-thumb-label">{thumbnail.label}</span>
                        </>
                      ) : (
                        <div className="empty-state history-thumb-empty">Loading preview…</div>
                      )}
                    </div>

                    <div className="history-row-copy">
                      <div className="history-row-headline">
                        <strong>{summary.asset_name}</strong>
                        <span
                          className={`status-pill status-pill-${getRunStatusTone(summary.status)}`}
                        >
                          <span className="status-pill-dot" />
                          {detail ? getStageLabel(detail) : getStatusLabel(summary.status)}
                        </span>
                      </div>
                      <p className="history-row-meta">
                        {getCollapsedRowMeta(summary, !selected)}
                      </p>
                    </div>
                  </button>

                  {selected ? (
                    <div className="history-row-detail">
                      <ExpandedRunSummary
                        title={title}
                        meta={meta}
                        status={detail ? getStageLabel(detail) : getStatusLabel(summary.status)}
                        statusTone={getRunStatusTone(summary.status)}
                        run={detail}
                        preparedImageUrl={
                          detail?.prepared_artifact
                            ? resolvePreparedArtifactUrl(detail.prepared_artifact.public_url)
                            : null
                        }
                        resultCapture={resultCapture}
                        sourceAsset={detail?.asset ?? null}
                        sourceInspectOpen={sourceInspectOpen}
                        onToggleSource={() =>
                          setHistorySourceInspectId((current) =>
                            current === summary.id ? null : summary.id,
                          )
                        }
                      />
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="workflow-layout">
      <div className="workflow-main">
        <section className="panel workflow-command-bar">
          {error ? <div className="banner">{error}</div> : null}

          <div className="workflow-command-row">
            <div className="workflow-command-copy">
              <p className="eyebrow">Workflow</p>
              <h2>{selectedAsset ? selectedAsset.name : "No staged source"}</h2>
              <div className="workflow-command-meta">
                <span>
                  {selectedAsset ? formatRunKindLabel(selectedAsset.kind) : "Stage a source"}
                </span>
                <span>
                  Drawable area{" "}
                  {plotterWorkspace
                    ? formatPhysicalSize(
                        plotterWorkspace.drawable_area_mm.width_mm,
                        plotterWorkspace.drawable_area_mm.height_mm,
                      )
                    : "unknown"}
                </span>
              </div>
            </div>

            <div className="workflow-actions">
              <label className="button-secondary file-button">
                {busyAction === "upload" ? "Uploading..." : "Upload SVG"}
                <input
                  type="file"
                  accept=".svg,image/svg+xml"
                  onChange={onFileChange}
                  disabled={busyAction !== null}
                />
              </label>
              <button
                type="button"
                className="button-secondary"
                onClick={() => void createBuiltInPattern()}
                disabled={busyAction !== null}
              >
                {busyAction === "pattern" ? "Building..." : "Load test-grid"}
              </button>
              <button
                type="button"
                className="button-primary"
                onClick={() => void startRun()}
                disabled={startDisabled}
              >
                {busyAction === "start" ? "Starting..." : "Start plot run"}
              </button>
            </div>
          </div>

          <div className={`workflow-status-line workflow-status-line-${workflowStatus.tone}`}>
            {workflowStatus.message}
          </div>

          {latestRunUsesDifferentSource ? (
            <p className="workflow-secondary-line">
              The latest completed run used a different source: {latestRun.asset.name}.
            </p>
          ) : null}
        </section>

        <WorkflowRunSummary
          displayRun={displayRun}
          selectedAsset={selectedAsset}
          latestCapture={latestCapture}
          sourceOpen={workflowSourceOpen}
          onToggleSource={() => setWorkflowSourceOpen((current) => !current)}
        />
      </div>
    </section>
  );
}
