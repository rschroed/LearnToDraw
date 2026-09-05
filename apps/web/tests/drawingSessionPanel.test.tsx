import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { DrawingSessionPanel } from "../src/features/plot-workflow/DrawingSessionPanel";
import type { DrawingSession } from "../src/types/drawing";
import type { PlotAsset } from "../src/types/plotting";

const initialAsset: PlotAsset = {
  id: "asset-initial",
  kind: "uploaded_svg",
  pattern_id: null,
  name: "First flower marks",
  timestamp: "2026-09-03T20:00:00Z",
  file_path: "/tmp/first.svg",
  public_url: "/plot-assets/first.svg",
  mime_type: "image/svg+xml",
};

const proposedAsset: PlotAsset = {
  ...initialAsset,
  id: "asset-proposal",
  kind: "generated_svg",
  name: "Flower pass 2",
  public_url: "/plot-assets/pass-2.svg",
};

function buildSession(status: DrawingSession["status"]): DrawingSession {
  const proposal = status === "proposal_ready"
    ? {
        interpretation: "The center is sparse; add three varied stems.",
        asset: proposedAsset,
        advisor_driver: "mock",
        advisor_model: "mock-advisor-v1",
        created_at: "2026-09-03T20:02:00Z",
        approved_at: null,
        approved_run_id: null,
      }
    : null;
  return {
    id: "session-1",
    session_version: 1,
    intent: "A lively field of flowers",
    mode: "additive",
    iteration_limit: 3,
    status,
    created_at: "2026-09-03T20:00:00Z",
    updated_at: "2026-09-03T20:02:00Z",
    iterations: [
      {
        number: 1,
        asset: initialAsset,
        run_id: "run-1",
        created_at: "2026-09-03T20:00:00Z",
        next_proposal: proposal,
      },
    ],
    advisor: {
      driver: "mock",
      available: true,
      model: "mock-advisor-v1",
      message: null,
    },
    error: null,
    plan: null,
    current_proposal: null,
    current_run_id: "run-1",
    assessing_run_id: null,
    pass_count: 1,
    planning_generation: 0,
    authorization: {
      approved_at: null,
      stop_requested: false,
      finish_requested: false,
      last_heartbeat_at: null,
    },
    paper_preflight: null,
    queued_guidance: [],
    requested_human_action: null,
    recovery_action: null,
    replanned_from_session_id: null,
    replanned_to_session_id: null,
    replan_context: null,
    events: [],
    approved_at: null,
    paused_at: null,
    completed_at: null,
    abandoned_at: null,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

it("creates a session, previews advice, and requires explicit approval to plot", async () => {
  const requests: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    requests.push(`${init?.method ?? "GET"} ${url}`);
    if (url === "/api/drawing-sessions/latest") {
      return Response.json({ session: null });
    }
    if (url === "/api/drawing-sessions" && init?.method === "POST") {
      return Response.json(buildSession("observed"));
    }
    if (url.endsWith("/advice") && init?.method === "POST") {
      return Response.json(buildSession("proposal_ready"));
    }
    if (url.endsWith("/iterations") && init?.method === "POST") {
      return Response.json(buildSession("running"));
    }
    throw new Error(`Unexpected request: ${url}`);
  });
  const onRunStarted = vi.fn(async () => undefined);
  render(
    <DrawingSessionPanel
      selectedAsset={initialAsset}
      plotStartBlocked={false}
      onRunStarted={onRunStarted}
    />,
  );

  fireEvent.change(screen.getByLabelText(/drawing intent/i), {
    target: { value: "A lively field of flowers" },
  });
  fireEvent.click(screen.getByRole("button", { name: /start session and plot first pass/i }));

  expect(await screen.findByText(/registered observation ready/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /request next pass/i }));

  expect(await screen.findByText(/the center is sparse/i)).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /proposed additive svg layer/i })).toHaveAttribute(
    "src",
    proposedAsset.public_url,
  );
  expect(screen.getByText(/adds permanent marks/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /plot proposed layer/i }));

  await waitFor(() => expect(onRunStarted).toHaveBeenCalledTimes(2));
  expect(requests).toContain("POST /api/drawing-sessions/session-1/advice");
  expect(requests).toContain("POST /api/drawing-sessions/session-1/iterations");
});
