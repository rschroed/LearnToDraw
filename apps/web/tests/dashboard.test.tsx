import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { App } from "../src/app/App";
import {
  createHardwareDashboardHarness,
  defaultAxiDrawHardwareStatus,
  installHardwareDashboardFetchMock,
} from "./hardwareDashboardTestUtils";

function buildRun({
  id,
  name,
  createdAt,
  observedCaptureId,
}: {
  id: string;
  name: string;
  createdAt: string;
  observedCaptureId?: string;
}) {
  return {
    id,
    status: observedCaptureId ? ("completed" as const) : ("plotting" as const),
    purpose: "normal" as const,
    capture_mode: "auto" as const,
    created_at: createdAt,
    updated_at: createdAt,
    asset: {
      id: `asset-${id}`,
      kind: "uploaded_svg" as const,
      pattern_id: null,
      name,
      timestamp: createdAt,
      file_path: `/tmp/${id}.svg`,
      public_url: `/plot-assets/${id}.svg`,
      mime_type: "image/svg+xml",
    },
    prepared_artifact: {
      file_path: `/tmp/${id}-prepared.svg`,
      public_url: `/plot-assets/${id}-prepared.svg`,
      mime_type: "image/svg+xml",
    },
    capture: observedCaptureId
      ? {
          id: observedCaptureId,
          timestamp: createdAt,
          file_path: `/tmp/${observedCaptureId}.jpg`,
          public_url: `/captures/${observedCaptureId}.jpg`,
          width: 1600,
          height: 1200,
          mime_type: "image/jpeg",
        }
      : null,
    observed_result: observedCaptureId
      ? {
          capture: {
            id: observedCaptureId,
            timestamp: createdAt,
            file_path: `/tmp/${observedCaptureId}.jpg`,
            public_url: `/captures/${observedCaptureId}.jpg`,
            width: 1600,
            height: 1200,
            mime_type: "image/jpeg",
          },
          camera_driver: "mock-camera",
          captured_at: createdAt,
          duration_ms: 900,
        }
      : null,
    error: null,
    stage_states: {
      prepare: {
        status: "completed" as const,
        started_at: createdAt,
        completed_at: createdAt,
        message: "Prepared.",
      },
      plot: {
        status: observedCaptureId ? ("completed" as const) : ("in_progress" as const),
        started_at: createdAt,
        completed_at: observedCaptureId ? createdAt : null,
        message: observedCaptureId ? "Plot completed." : "Plotting.",
      },
      capture: {
        status: observedCaptureId ? ("completed" as const) : ("pending" as const),
        started_at: observedCaptureId ? createdAt : null,
        completed_at: observedCaptureId ? createdAt : null,
        message: observedCaptureId ? "Captured." : "Waiting.",
      },
    },
    plotter_run_details: {
      preparation: {
        source_width: 120,
        source_height: 90,
        prepared_width_mm: 110,
        prepared_height_mm: 82,
        preparation_audit: {
          prepared_within_drawable_area: true,
        },
      },
    },
    camera_run_details: {},
  };
}

function formatShortTimestamp(timestamp: string) {
  const date = new Date(timestamp);
  return `${date.toLocaleDateString([], {
    month: "numeric",
    day: "numeric",
  })} · ${date.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  })}`;
}

describe("workflow-first dashboard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("lands on the Workflow view by default", async () => {
    const harness = createHardwareDashboardHarness();
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: /workflow-first local operator/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^workflow$/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("heading", { name: /^result$/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /prepared and result/i }),
    ).not.toBeInTheDocument();
  });

  it("shows a global blocker when the saved workspace no longer fits the machine", async () => {
    const harness = createHardwareDashboardHarness({
      currentWorkspace: {
        ...createHardwareDashboardHarness().currentWorkspace,
        is_valid: false,
        validation_error: "Configured page width exceeds the plotter bounds width.",
      },
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    expect(
      await screen.findByText(/paper setup needs attention before plotting/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/configured page width exceeds the plotter bounds width/i),
    ).toBeInTheDocument();
  });

  it("uses the latest global capture as the observed fallback when no run is selected", async () => {
    const harness = createHardwareDashboardHarness({
      latestCapture: {
        id: "capture-global-001",
        timestamp: "2026-03-15T20:05:00Z",
        file_path: "/tmp/capture-global-001.jpg",
        public_url: "/captures/capture-global-001.jpg",
        width: 1920,
        height: 1080,
        mime_type: "image/jpeg",
      },
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    expect(
      await screen.findByRole("img", {
        name: /latest result capture capture-global-001/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/latest saved result/i)).toBeInTheDocument();
    expect(screen.getByText(/captured · 1920 × 1080/i)).toBeInTheDocument();
  });

  it("prioritizes the selected run observed output over the latest global capture", async () => {
    const latestRun = buildRun({
      id: "run-001",
      name: "Loop Study",
      createdAt: "2026-03-15T20:04:00Z",
      observedCaptureId: "capture-run-001",
    });
    const harness = createHardwareDashboardHarness({
      latestRun,
      latestCapture: {
        id: "capture-global-002",
        timestamp: "2026-03-15T20:06:00Z",
        file_path: "/tmp/capture-global-002.jpg",
        public_url: "/captures/capture-global-002.jpg",
        width: 1920,
        height: 1080,
        mime_type: "image/jpeg",
      },
      recentRuns: [
        {
          id: latestRun.id,
          status: latestRun.status,
          purpose: latestRun.purpose,
          created_at: latestRun.created_at,
          updated_at: latestRun.updated_at,
          asset_id: latestRun.asset.id,
          asset_name: latestRun.asset.name,
          asset_kind: latestRun.asset.kind,
          error: null,
        },
      ],
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    expect(
      await screen.findByRole("img", {
        name: /result image for run run-001/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("img", { name: /latest result capture capture-global-002/i }),
    ).not.toBeInTheDocument();
  });

  it("keeps the source hidden by default and reveals it on demand in the Workflow view", async () => {
    const latestRun = buildRun({
      id: "run-010",
      name: "Contour Study",
      createdAt: "2026-03-15T21:04:00Z",
      observedCaptureId: "capture-run-010",
    });
    const harness = createHardwareDashboardHarness({
      latestRun,
      recentRuns: [
        {
          id: latestRun.id,
          status: latestRun.status,
          purpose: latestRun.purpose,
          created_at: latestRun.created_at,
          updated_at: latestRun.updated_at,
          asset_id: latestRun.asset.id,
          asset_name: latestRun.asset.name,
          asset_kind: latestRun.asset.kind,
          error: null,
        },
      ],
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    expect(
      await screen.findByRole("img", { name: /prepared output for run run-010/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^result$/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /^source$/i })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^details$/i })).toBeInTheDocument();
    expect(screen.getByText(/prepared ✓/i)).toBeInTheDocument();
    expect(screen.getByText(/plotted ✓/i)).toBeInTheDocument();
    expect(screen.getByText(/captured ✓/i)).toBeInTheDocument();
    expect(
      screen.getByText((content) => content.includes(formatShortTimestamp(latestRun.created_at))),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /view source/i }));

    expect(
      await screen.findByRole("img", { name: /source reference contour study/i }),
    ).toBeInTheDocument();
  });

  it("keeps machine controls on the Machine tab", async () => {
    const harness = createHardwareDashboardHarness({
      currentHardwareStatus: structuredClone(defaultAxiDrawHardwareStatus),
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /^machine$/i }));

    expect(await screen.findByRole("heading", { name: /paper setup/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /current setup/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/latest capture/i)).not.toBeInTheDocument();
    expect(screen.getAllByLabelText(/paper setup preview/i)).toHaveLength(1);
    expect(screen.getByRole("heading", { name: /^plotter$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /capture test image/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save paper setup/i })).toBeInTheDocument();
    expect(screen.getByText(/diagnostics/i).closest("details")).not.toHaveAttribute("open");
  });

  it("renders the History view as expandable run rows", async () => {
    const latestRun = buildRun({
      id: "run-new",
      name: "Newest Loop",
      createdAt: "2026-03-15T20:10:00Z",
      observedCaptureId: "capture-new",
    });
    const olderRun = buildRun({
      id: "run-old",
      name: "Older Grid",
      createdAt: "2026-03-14T18:00:00Z",
      observedCaptureId: "capture-old",
    });
    const harness = createHardwareDashboardHarness({
      latestRun,
      recentRuns: [
        {
          id: latestRun.id,
          status: latestRun.status,
          purpose: latestRun.purpose,
          created_at: latestRun.created_at,
          updated_at: latestRun.updated_at,
          asset_id: latestRun.asset.id,
          asset_name: latestRun.asset.name,
          asset_kind: latestRun.asset.kind,
          error: null,
        },
        {
          id: olderRun.id,
          status: olderRun.status,
          purpose: olderRun.purpose,
          created_at: olderRun.created_at,
          updated_at: olderRun.updated_at,
          asset_id: olderRun.asset.id,
          asset_name: olderRun.asset.name,
          asset_kind: olderRun.asset.kind,
          error: null,
        },
      ],
      plotRunsById: {
        [olderRun.id]: olderRun,
      },
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /^history$/i }));

    expect(await screen.findByText(/recent runs/i)).toBeInTheDocument();
    expect(screen.getByText(/newest loop/i)).toBeInTheDocument();
    expect(screen.getByText(/older grid/i)).toBeInTheDocument();
    const olderRowButton = await screen.findByRole("button", { name: /older grid/i });
    const olderRow = olderRowButton.closest("article");
    expect(olderRow).not.toBeNull();
    expect(within(olderRow as HTMLElement).getByText(/uploaded svg/i)).toBeInTheDocument();
    expect(within(olderRow as HTMLElement).queryByText(/capture saved/i)).not.toBeInTheDocument();
    expect(within(olderRow as HTMLElement).queryByText(/run-old/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /timeline and sizing/i })).not.toBeInTheDocument();

    fireEvent.click(olderRowButton);

    await waitFor(() => {
      expect(
        screen.getByRole("img", { name: /prepared output for run run-old/i }),
      ).toBeInTheDocument();
    });
    expect(screen.queryByRole("heading", { name: /observed/i })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^result$/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^details$/i })).toBeInTheDocument();
    expect(screen.getByText(/prepared ✓/i)).toBeInTheDocument();
    expect(screen.getByText(/plotted ✓/i)).toBeInTheDocument();
    expect(screen.getByText(/captured ✓/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /^source$/i })).not.toBeInTheDocument();
    expect(
      screen.getByText((content) => content.includes(formatShortTimestamp(olderRun.created_at))),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /view source/i }));

    expect(
      await screen.findByRole("img", { name: /source reference older grid/i }),
    ).toBeInTheDocument();
  });
});
