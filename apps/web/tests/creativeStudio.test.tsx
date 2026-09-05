import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { App } from "../src/app/App";
import { StudioCanvas } from "../src/features/studio/StudioCanvas";
import { StudioProgressPanel } from "../src/features/studio/StudioProgressPanel";
import type {
  DrawingSession,
  DrawingSessionEvent,
  DrawingSessionStatus,
} from "../src/types/drawing";
import type { CaptureMetadata } from "../src/types/hardware";
import type { PlotAsset, PlotRun } from "../src/types/plotting";
import {
  createHardwareDashboardHarness,
  defaultAxiDrawHardwareStatus,
  installHardwareDashboardFetchMock,
} from "./hardwareDashboardTestUtils";

const now = "2026-09-04T20:00:00Z";

const asset: PlotAsset = {
  id: "asset-1",
  kind: "generated_svg",
  pattern_id: null,
  name: "Whimsical flowers — first pass",
  timestamp: now,
  file_path: "/tmp/asset-1.svg",
  public_url: "/plot-assets/asset-1.svg",
  mime_type: "image/svg+xml",
};

function event(
  type: DrawingSessionEvent["type"],
  message: string,
  details: Record<string, unknown> = {},
): DrawingSessionEvent {
  return {
    id: `${type}-${message}`,
    type,
    created_at: now,
    message,
    asset_id: null,
    run_id: type === "session_created" ? null : "run-1",
    details,
  };
}

function buildSession(
  status: DrawingSessionStatus,
  overrides: Partial<DrawingSession> = {},
): DrawingSession {
  const approved = !["planning", "awaiting_approval"].includes(status);
  const hasRun = approved;
  return {
    id: "session-1",
    session_version: 2,
    intent: "A whimsical field of flowers",
    mode: "additive",
    iteration_limit: null,
    status,
    created_at: now,
    updated_at: now,
    iterations: hasRun
      ? [{ number: 1, asset, run_id: "run-1", created_at: now, next_proposal: null }]
      : [],
    advisor: {
      driver: "mock",
      available: true,
      model: "mock-advisor-v1",
      message: null,
    },
    error: status === "paused" ? "The camera observation needs attention." : null,
    plan:
      status === "planning"
        ? null
        : {
            summary: "Build an airy cluster from varied stems and a loose center.",
            paper_strategy: "Keep the composition centered with generous breathing room.",
            completion_intent: "Stop when the field feels lively without filling every gap.",
          },
    current_proposal:
      status === "planning"
        ? null
        : {
            asset,
            created_at: now,
            advisor_driver: "mock",
            advisor_model: "mock-advisor-v1",
          },
    current_run_id: hasRun ? "run-1" : null,
    assessing_run_id: null,
    pass_count: hasRun ? 1 : 0,
    planning_generation: 1,
    authorization: {
      approved_at: approved ? now : null,
      stop_requested: status === "stopping",
      finish_requested: false,
      last_heartbeat_at: approved ? now : null,
    },
    paper_preflight: approved
      ? {
          confirmed_at: now,
          page_width_mm: 279.4,
          page_height_mm: 215.9,
          drawable_width_mm: 259.4,
          drawable_height_mm: 195.9,
        }
      : null,
    queued_guidance: [],
    requested_human_action: null,
    events: [
      event("session_created", "Creative session created. Planning the first pass."),
      ...(status === "planning"
        ? []
        : [event("plan_ready", "The drawing plan and first-pass preview are ready.")]),
      ...(approved ? [event("session_approved", "Open-ended drawing approved.")] : []),
    ],
    approved_at: approved ? now : null,
    paused_at: status === "paused" ? now : null,
    completed_at: status === "completed" ? now : null,
    abandoned_at: status === "abandoned" ? now : null,
    ...overrides,
  };
}

function buildCapture(reviewStatus: "pending" | "confirmed" = "confirmed"): CaptureMetadata {
  const corners = {
    top_left: [100, 100] as [number, number],
    top_right: [1500, 100] as [number, number],
    bottom_right: [1500, 1100] as [number, number],
    bottom_left: [100, 1100] as [number, number],
  };
  return {
    id: "capture-1",
    timestamp: now,
    file_path: "/tmp/capture-1.jpg",
    public_url: "/captures/capture-1.jpg",
    width: 1600,
    height: 1200,
    mime_type: "image/jpeg",
    review: {
      registration_version: 2,
      review_mode: "manual_corners",
      review_required: reviewStatus === "pending",
      review_status: reviewStatus,
      proposed_corners: corners,
      confirmed_corners: reviewStatus === "confirmed" ? corners : null,
      confirmation_source: reviewStatus === "confirmed" ? "manual" : null,
    },
    normalized:
      reviewStatus === "confirmed"
        ? {
            rectified_color_url: "/captures/capture-1-color.png",
            rectified_grayscale_url: "/captures/capture-1-gray.png",
            debug_overlay_url: "/captures/capture-1-debug.png",
            metadata: {
              method: "manual_corners_v2",
              confidence: null,
              corners,
              transform: {
                matrix: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                inverse_matrix: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                source_space: "raw_capture_px",
                destination_space: "page_px",
                pixels_per_mm_x: 8,
                pixels_per_mm_y: 8,
              },
              output: { width: 2048, height: 1583, aspect_ratio: 1.294 },
              target_frame_source: "prepared_svg",
              frame: {
                kind: "page_aligned",
                version: 2,
                page_width_mm: 279.4,
                page_height_mm: 215.9,
                origin: "top-left",
              },
            },
          }
        : null,
  };
}

function buildRun(
  status: PlotRun["status"] = "plotting",
  capture: CaptureMetadata | null = null,
): PlotRun {
  const plotComplete = !["pending", "plotting", "stopping"].includes(status);
  return {
    id: "run-1",
    status,
    purpose: "normal",
    capture_mode: "auto",
    created_at: now,
    updated_at: now,
    asset,
    prepared_artifact: {
      file_path: "/tmp/run-1-prepared.svg",
      public_url: "/plot-run-artifacts/run-1-prepared.svg",
      mime_type: "image/svg+xml",
    },
    capture,
    capture_attempts: [],
    observed_result:
      capture?.review?.review_status === "confirmed"
        ? { capture, camera_driver: "mock-camera", captured_at: now, duration_ms: 200 }
        : null,
    progress_artifact: null,
    interruption_reason: null,
    error: status === "failed" ? "Capture failed." : null,
    stage_states: {
      prepare: { status: "completed", started_at: now, completed_at: now, message: "Prepared." },
      plot: {
        status: plotComplete ? "completed" : "in_progress",
        started_at: now,
        completed_at: plotComplete ? now : null,
        message: plotComplete ? "Plotted." : "Plotting.",
      },
      capture: {
        status: capture ? "completed" : status === "failed" ? "failed" : "pending",
        started_at: capture || status === "failed" ? now : null,
        completed_at: capture || status === "failed" ? now : null,
        message: status === "failed" ? "Capture failed." : null,
      },
      capture_review: {
        status:
          status === "awaiting_capture_review"
            ? "in_progress"
            : capture?.review?.review_status === "confirmed"
              ? "completed"
              : "pending",
        started_at: capture ? now : null,
        completed_at: capture?.review?.review_status === "confirmed" ? now : null,
        message: null,
      },
    },
    plotter_run_details: {
      preparation: { page_width_mm: 279.4, page_height_mm: 215.9 },
    },
    camera_run_details: {},
  };
}

function installStudioMock(
  initialSession: DrawingSession,
  run: PlotRun | null = null,
) {
  let currentSession = initialSession;
  let currentRun = run;
  const requests: Array<{ method: string; url: string; body?: string }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    requests.push({ method, url, body: typeof init?.body === "string" ? init.body : undefined });

    if (url === "/api/hardware/status") return Response.json(defaultAxiDrawHardwareStatus);
    if (url === "/api/drawing-sessions/latest" && method === "GET") {
      return Response.json({ session: currentSession });
    }
    if (url === "/api/plotter/workspace") {
      return Response.json({
        plotter_bounds_mm: { width_mm: 289.974, height_mm: 207.932 },
        page_size_mm: { width_mm: 279.4, height_mm: 215.9 },
        margins_mm: { left_mm: 10, top_mm: 10, right_mm: 10, bottom_mm: 10 },
        drawable_area_mm: { width_mm: 259.4, height_mm: 195.9 },
        updated_at: now,
        source: "persisted",
        is_valid: true,
        validation_error: null,
      });
    }
    if (url === `/api/drawing-sessions/${currentSession.id}` && method === "GET") {
      return Response.json(currentSession);
    }
    if (url === `/api/plot-runs/${currentRun?.id}` && method === "GET" && currentRun) {
      return Response.json(currentRun);
    }
    if (url.endsWith("/capture-review") && method === "GET" && currentRun?.capture?.review) {
      return Response.json({
        run_id: currentRun.id,
        capture: currentRun.capture,
        review: currentRun.capture.review,
      });
    }
    if (url.endsWith("/heartbeat") && method === "POST") return Response.json(currentSession);
    if (url.endsWith("/messages") && method === "POST") {
      const text = JSON.parse(String(init?.body)).text as string;
      currentSession = {
        ...currentSession,
        status: currentSession.authorization.approved_at ? currentSession.status : "planning",
        plan: currentSession.authorization.approved_at ? currentSession.plan : null,
        current_proposal: currentSession.authorization.approved_at
          ? currentSession.current_proposal
          : null,
        queued_guidance: [...currentSession.queued_guidance, text],
        events: [...currentSession.events, event("user_guidance", text)],
      };
      return Response.json(currentSession);
    }
    if (url.endsWith("/approve") && method === "POST") {
      currentSession = buildSession("running");
      currentRun = buildRun("plotting");
      return Response.json(currentSession);
    }
    if (url.endsWith("/finish") && method === "POST") {
      currentSession = {
        ...currentSession,
        status: "completed",
        completed_at: now,
        paused_at: null,
        authorization: {
          ...currentSession.authorization,
          stop_requested: false,
          finish_requested: false,
        },
        events: [
          ...currentSession.events,
          event("session_completed", "Finished by you after the current pass.", {
            source: "user",
          }),
        ],
      };
      return Response.json(currentSession);
    }
    if (url.endsWith("/abandon") && method === "POST") {
      currentSession = {
        ...currentSession,
        status: "abandoned",
        abandoned_at: now,
        error: null,
        queued_guidance: [],
        events: [
          ...currentSession.events,
          event("session_abandoned", "This session was left unfinished."),
        ],
      };
      return Response.json(currentSession);
    }
    if (url.endsWith("/stop") && method === "POST") {
      currentSession = {
        ...currentSession,
        status: "stopping",
        authorization: { ...currentSession.authorization, stop_requested: true },
      };
      return Response.json(currentSession);
    }
    if (url.endsWith("/capture/retry") && method === "POST" && currentRun) {
      currentRun = { ...currentRun, status: "capturing", error: null };
      return Response.json(currentRun);
    }
    if (url.endsWith("/resume") && method === "POST") {
      currentSession = { ...currentSession, status: "running", error: null, paused_at: null };
      return Response.json(currentSession);
    }
    throw new Error(`Unexpected request: ${method} ${url}`);
  });
  return { requests, getSession: () => currentSession };
}

beforeEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/");
  Object.defineProperty(window, "scrollTo", { value: vi.fn(), writable: true });
});

it("starts with creative intent and creates a prompt-only planning session", async () => {
  const currentSession = buildSession("planning");
  const requests: Array<{ method: string; url: string; body?: string }> = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    requests.push({ method, url, body: typeof init?.body === "string" ? init.body : undefined });
    if (url === "/api/hardware/status") return Response.json(defaultAxiDrawHardwareStatus);
    if (url === "/api/drawing-sessions/latest") return Response.json({ session: null });
    if (url === "/api/drawing-sessions" && method === "POST") return Response.json(currentSession);
    if (url === `/api/drawing-sessions/${currentSession.id}`) return Response.json(currentSession);
    throw new Error(`Unexpected request: ${method} ${url}`);
  });

  render(<App />);
  expect(await screen.findByRole("heading", { name: /what should we draw/i })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/drawing idea/i), {
    target: { value: "A field of unruly flowers" },
  });
  const createButton = screen.getByRole("button", { name: /create a drawing/i });
  await waitFor(() => expect(createButton).toBeEnabled());
  fireEvent.click(createButton);

  expect(await screen.findByRole("heading", { name: /finding the first useful marks/i })).toBeInTheDocument();
  const createRequest = requests.find(
    (request) => request.url === "/api/drawing-sessions" && request.method === "POST",
  );
  expect(JSON.parse(createRequest?.body ?? "{}")).toEqual({
    intent: "A field of unruly flowers",
    mode: "additive",
  });
  expect(requests.some((request) => request.url === "/api/plot-runs")).toBe(false);
});

it("keeps the deliberate new-drawing route on a blank prompt", async () => {
  window.history.replaceState({}, "", "/new");
  installStudioMock(buildSession("paused"), buildRun("completed", buildCapture()));

  render(<App />);

  expect(
    await screen.findByRole("heading", { name: /what should we draw/i }),
  ).toBeInTheDocument();
  expect(window.location.pathname).toBe("/new");
});

it("shows the plan, explains open-ended approval, and lets a message replace the proposal", async () => {
  window.history.replaceState({}, "", "/sessions/session-1");
  const harness = installStudioMock(buildSession("awaiting_approval"));
  render(<App />);

  const planHeading = await screen.findByRole("heading", { name: /build an airy cluster/i });
  await waitFor(() => expect(planHeading).toHaveFocus());
  expect(screen.getByRole("img", { name: /proposed first drawing pass/i })).toBeInTheDocument();
  expect(screen.getByText(/authorizes an attended sequence/i)).toBeInTheDocument();
  expect(screen.getByText(/more than one permanent layer/i)).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText(/revise the plan/i), {
    target: { value: "Leave more room on the right" },
  });
  fireEvent.click(screen.getByRole("button", { name: /revise plan/i }));

  expect(await screen.findByRole("heading", { name: /finding the first useful marks/i })).toBeInTheDocument();
  expect(screen.queryByRole("img", { name: /proposed first drawing pass/i })).not.toBeInTheDocument();
  expect(
    harness.requests.some(
      (request) => request.url.endsWith("/messages") && request.body?.includes("room on the right"),
    ),
  ).toBe(true);
});

it("requires a paper and pen preflight before first motion", async () => {
  window.history.replaceState({}, "", "/sessions/session-1");
  const harness = installStudioMock(buildSession("awaiting_approval"));
  render(<App />);

  const approve = await screen.findByRole("button", { name: /approve and begin/i });
  expect(approve).toBeDisabled();
  expect(screen.getByText(/279.4 × 215.9 mm · landscape/i)).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("checkbox", { name: /blank sheet loaded in this orientation/i }),
  );
  expect(approve).toBeEnabled();
  fireEvent.click(approve);

  await waitFor(() => {
    const request = harness.requests.find((item) => item.url.endsWith("/approve"));
    expect(JSON.parse(request?.body ?? "{}")).toEqual({ paper_ready: true });
  });
});

it("abandons an unused plan before opening a blank new drawing", async () => {
  window.history.replaceState({}, "", "/sessions/session-1");
  const harness = installStudioMock(buildSession("awaiting_approval"));
  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: /new drawing/i }));
  const dialog = screen.getByRole("dialog", { name: /leave this draft/i });
  expect(within(dialog).getByText(/nothing has been plotted/i)).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: /abandon and start new/i }));

  expect(
    await screen.findByRole("heading", { name: /what should we draw/i }),
  ).toBeInTheDocument();
  expect(window.location.pathname).toBe("/new");
  expect(harness.requests.some((request) => request.url.endsWith("/abandon"))).toBe(true);
});

it("lets the user finish a safely paused drawing", async () => {
  window.history.replaceState({}, "", "/sessions/session-1");
  const harness = installStudioMock(buildSession("paused"), buildRun("completed", buildCapture()));
  render(<App />);

  fireEvent.click(await screen.findByRole("button", { name: /^finish drawing$/i }));
  await waitFor(() => {
    expect(harness.requests.some((request) => request.url.endsWith("/finish"))).toBe(true);
  });
  expect(
    await screen.findAllByText(/finished by you after the current pass/i),
  ).not.toHaveLength(0);
});

it("queues active guidance, sends heartbeats, and confirmation-protects emergency stop", async () => {
  window.history.replaceState({}, "", "/sessions/session-1");
  const harness = installStudioMock(buildSession("running"), buildRun("plotting"));
  render(<App />);

  expect(await screen.findByText(/the studio is authorized to continue/i)).toBeInTheDocument();
  await waitFor(() => {
    expect(harness.requests.some((request) => request.url.endsWith("/heartbeat"))).toBe(true);
  });

  fireEvent.change(screen.getByLabelText(/guidance for the next observation/i), {
    target: { value: "Make the flowers less regular" },
  });
  fireEvent.click(screen.getByRole("button", { name: /queue guidance/i }));
  expect(await screen.findByText("1 queued")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: /^emergency stop$/i }));
  const dialog = screen.getByRole("alertdialog", { name: /pause the active plot/i });
  expect(within(dialog).getByText(/after its current path segment/i)).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: /pause after current segment/i }));

  await waitFor(() => {
    const stopRequest = harness.requests.find((request) => request.url.endsWith("/stop"));
    expect(JSON.parse(stopRequest?.body ?? "{}")).toEqual({ mode: "emergency" });
  });
});

it("explains each creative run stage in human terms", () => {
  const { rerender } = render(
    <StudioProgressPanel session={buildSession("planning")} run={null} />,
  );
  expect(screen.getByRole("heading", { name: /planning the first pass/i })).toBeInTheDocument();
  expect(screen.getByText(/nothing will move yet/i)).toBeInTheDocument();
  expect(screen.getByText("Plan").closest("li")).toHaveAttribute("aria-current", "step");

  rerender(<StudioProgressPanel session={buildSession("awaiting_approval")} run={null} />);
  expect(screen.getByRole("heading", { name: /preview ready for approval/i })).toBeInTheDocument();

  const preparingRun = buildRun("pending");
  preparingRun.stage_states.prepare = {
    status: "in_progress",
    started_at: now,
    completed_at: null,
    message: "Preparing.",
  };
  rerender(<StudioProgressPanel session={buildSession("running")} run={preparingRun} />);
  expect(screen.getByRole("heading", { name: /preparing pass 1/i })).toBeInTheDocument();

  rerender(
    <StudioProgressPanel session={buildSession("running")} run={buildRun("plotting")} />,
  );
  expect(screen.getByRole("heading", { name: /drawing pass 1/i })).toBeInTheDocument();
  expect(screen.getByText("Draw").closest("li")).toHaveAttribute("aria-current", "step");

  const capturingRun = buildRun("capturing");
  capturingRun.stage_states.capture = {
    status: "in_progress",
    started_at: now,
    completed_at: null,
    message: "Capturing.",
  };
  rerender(<StudioProgressPanel session={buildSession("running")} run={capturingRun} />);
  expect(screen.getByRole("heading", { name: /photographing pass 1/i })).toBeInTheDocument();

  rerender(
    <StudioProgressPanel
      session={buildSession("awaiting_capture_review")}
      run={buildRun("awaiting_capture_review", buildCapture("pending"))}
    />,
  );
  expect(screen.getByRole("heading", { name: /page registration needed for pass 1/i })).toBeInTheDocument();
  expect(screen.getByText("Register").closest("li")).toHaveAttribute("aria-current", "step");

  rerender(
    <StudioProgressPanel
      session={buildSession("running", { assessing_run_id: "run-1" })}
      run={buildRun("completed", buildCapture())}
    />,
  );
  expect(screen.getByRole("heading", { name: /looking at pass 1/i })).toBeInTheDocument();
  expect(screen.getByText("Reflect").closest("li")).toHaveAttribute("aria-current", "step");

  rerender(
    <StudioProgressPanel session={buildSession("stopping")} run={buildRun("stopping")} />,
  );
  expect(screen.getByRole("heading", { name: /stopping safely/i })).toBeInTheDocument();

  rerender(<StudioProgressPanel session={buildSession("paused")} run={buildRun("failed")} />);
  expect(screen.getByRole("heading", { name: /session paused/i })).toBeInTheDocument();

  rerender(<StudioProgressPanel session={buildSession("failed")} run={buildRun("failed")} />);
  expect(screen.getByRole("heading", { name: /session stopped/i })).toBeInTheDocument();

  rerender(<StudioProgressPanel session={buildSession("completed")} run={buildRun("completed")} />);
  expect(screen.getByRole("heading", { name: /drawing complete/i })).toBeInTheDocument();
  expect(screen.getByText(/1 pass complete/i)).toBeInTheDocument();
});

it("offers capture-only recovery and never creates a replacement plot run", async () => {
  window.history.replaceState({}, "", "/sessions/session-1");
  const failedRun = buildRun("failed");
  const harness = installStudioMock(buildSession("paused"), failedRun);
  render(<App />);

  const recoveryHeading = await screen.findByRole("heading", { name: /safely paused/i });
  await waitFor(() => expect(recoveryHeading).toHaveFocus());
  fireEvent.click(screen.getByRole("button", { name: /retake photo only/i }));

  await waitFor(() => {
    expect(harness.requests.some((request) => request.url.endsWith("/capture/retry"))).toBe(true);
  });
  expect(
    harness.requests.some(
      (request) => request.url === "/api/plot-runs" && request.method === "POST",
    ),
  ).toBe(false);
});

it("retakes a questionable registration frame without replotting", async () => {
  window.history.replaceState({}, "", "/sessions/session-1");
  const pendingRun = buildRun("awaiting_capture_review", buildCapture("pending"));
  const harness = installStudioMock(buildSession("awaiting_capture_review"), pendingRun);
  render(<App />);

  expect(await screen.findByText(/manual page registration required/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /retake photo only/i }));

  await waitFor(() => {
    expect(harness.requests.some((request) => request.url.endsWith("/capture/retry"))).toBe(true);
  });
  expect(
    harness.requests.some(
      (request) => request.url === "/api/plot-runs" && request.method === "POST",
    ),
  ).toBe(false);
});

it("uses the configured landscape page orientation before a plot run exists", async () => {
  window.history.replaceState({}, "", "/sessions/session-1");
  installStudioMock(buildSession("awaiting_approval"));
  const { container } = render(<App />);

  expect(
    await screen.findByRole("heading", { name: /what we intend to draw/i }),
  ).toBeInTheDocument();
  await waitFor(() => {
    const paper = container.querySelector<HTMLElement>(".studio-paper");
    expect(paper).not.toBeNull();
    expect(Number(paper?.style.aspectRatio)).toBeCloseTo(279.4 / 215.9);
  });
});

it("renders a true V2 overlay and exposes manual registration when required", async () => {
  const observedCapture = buildCapture("confirmed");
  const completedRun = buildRun("completed", observedCapture);
  const completedSession = buildSession("completed", {
    events: [
      event("agent_decision", "The composition has enough life.", {
        assessment: "The varied stems now read as a field.",
        decision: "complete",
      }),
      event("session_completed", "The drawing feels complete."),
    ],
  });
  const { rerender } = render(
    <StudioCanvas
      session={completedSession}
      runs={{ "run-1": completedRun }}
      captureReview={null}
      busy={false}
      retryingCapture={false}
      error={null}
      onConfirmRegistration={async () => undefined}
      onRetryCapture={async () => undefined}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: /^overlay$/i }));
  expect(screen.getByRole("heading", { name: /intended versus observed/i })).toBeInTheDocument();
  const slider = screen.getByRole("slider", { name: /intended opacity/i });
  fireEvent.change(slider, { target: { value: "72" } });
  expect(slider).toHaveValue("72");

  const pendingCapture = buildCapture("pending");
  const pendingRun = buildRun("awaiting_capture_review", pendingCapture);
  const retryCapture = vi.fn(async () => undefined);
  rerender(
    <StudioCanvas
      session={buildSession("awaiting_capture_review")}
      runs={{ "run-1": pendingRun }}
      captureReview={{ run_id: "run-1", capture: pendingCapture, review: pendingCapture.review! }}
      busy={false}
      retryingCapture={false}
      error={null}
      onConfirmRegistration={async () => undefined}
      onRetryCapture={retryCapture}
    />,
  );
  expect(await screen.findByText(/manual page registration required/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /register page/i })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /retake photo only/i }));
  expect(retryCapture).toHaveBeenCalledWith("run-1");
});

it("lists session-level work in Gallery and keeps the full operator surface in Controls", async () => {
  window.history.replaceState({}, "", "/gallery");
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
    Response.json({
      sessions: [
        {
          id: "session-1",
          session_version: 2,
          intent: "A whimsical field of flowers",
          status: "completed",
          pass_count: 3,
          created_at: now,
          updated_at: now,
          preview_url: "/captures/final-gray.png",
        },
      ],
    }),
  );
  const { unmount } = render(<App />);
  expect(await screen.findByRole("heading", { name: /drawings made through observation/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /whimsical field of flowers/i })).toBeInTheDocument();
  expect(screen.getByText(/3 passes/i)).toBeInTheDocument();
  unmount();

  window.history.replaceState({}, "", "/controls");
  const controlsHarness = createHardwareDashboardHarness();
  installHardwareDashboardFetchMock(controlsHarness);
  render(<App />);
  expect(await screen.findByRole("heading", { name: /machine setup and manual work/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /upload, plot, capture, and inspect an svg/i })).toBeInTheDocument();
  expect(screen.getByLabelText(/upload svg/i)).toHaveAttribute("type", "file");
});

it("configures the OpenAI advisor in backend memory and clears the key field", async () => {
  window.history.replaceState({}, "", "/controls");
  const controlsHarness = createHardwareDashboardHarness({
    advisorConfiguration: {
      advisor: {
        driver: "disabled",
        available: false,
        model: null,
        message: "Drawing advisor is disabled on the local backend.",
      },
      source: "startup",
      persistence: "process_memory",
      clears_on_restart: true,
    },
  });
  installHardwareDashboardFetchMock(controlsHarness);
  render(<App />);

  const apiKey = "sk-test-browser-secret";
  const keyInput = await screen.findByLabelText(/openai api key/i);
  const modelInput = screen.getByLabelText(/^model$/i);
  fireEvent.change(keyInput, { target: { value: apiKey } });
  fireEvent.change(modelInput, { target: { value: "gpt-5.6-terra" } });
  fireEvent.click(screen.getByRole("button", { name: /enable openai advisor/i }));

  await waitFor(() => {
    expect(controlsHarness.advisorConfigurationRequests).toEqual([
      { api_key: apiKey, model: "gpt-5.6-terra" },
    ]);
  });
  expect(keyInput).toHaveValue("");
  expect(screen.getByText(/loaded in backend memory/i)).toBeInTheDocument();
  expect(screen.queryByDisplayValue(apiKey)).not.toBeInTheDocument();
  expect(window.localStorage.getItem("OPENAI_API_KEY")).toBeNull();

  fireEvent.click(screen.getByRole("button", { name: /clear runtime key/i }));
  await waitFor(() => expect(controlsHarness.advisorConfigurationClears).toBe(1));
  expect(screen.getByText(/runtime openai configuration cleared/i)).toBeInTheDocument();
});

it("surfaces provider-disabled recovery without exposing a browser key field", async () => {
  window.history.replaceState({}, "", "/sessions/session-1");
  const paused = buildSession("paused", {
    advisor: {
      driver: "disabled",
      available: false,
      model: null,
      message: "Drawing advisor is disabled on the local backend.",
    },
  });
  installStudioMock(paused, buildRun("failed"));
  render(<App />);

  expect(await screen.findByText(/creative advisor unavailable/i)).toBeInTheDocument();
  expect(screen.getByText(/disabled on the local backend/i)).toBeInTheDocument();
  expect(screen.queryByLabelText(/api key/i)).not.toBeInTheDocument();
});
