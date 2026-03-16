import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { App } from "../src/app/App";

const hardwareStatus = {
  plotter: {
    available: true,
    connected: true,
    busy: false,
    error: null,
    driver: "mock-plotter",
    last_updated: "2026-03-15T20:00:00Z",
    details: {
      model: "mock-pen-plotter",
      workspace: "A4",
      position: "origin",
    },
  },
  camera: {
    available: true,
    connected: true,
    busy: false,
    error: null,
    driver: "mock-camera",
    last_updated: "2026-03-15T20:00:00Z",
    details: {
      resolution: "1280x960",
      last_capture_id: null,
    },
  },
};

const axidrawHardwareStatus = {
  ...hardwareStatus,
  plotter: {
    ...hardwareStatus.plotter,
    driver: "axidraw-pyapi",
    details: {
      ...hardwareStatus.plotter.details,
      api_surface: "installed_axidrawinternal_compat",
      pen_tuning: {
        pen_pos_up: 60,
        pen_pos_down: 30,
        pen_rate_raise: 75,
      },
      last_test_action: null,
      last_test_action_status: null,
    },
  },
};

describe("Hardware dashboard", () => {
  let latestCapture: null | {
    id: string;
    timestamp: string;
    file_path: string;
    public_url: string;
    width: number;
    height: number;
    mime_type: string;
  };
  let latestRun:
    | null
    | {
        id: string;
        status: "pending" | "plotting" | "capturing" | "completed";
        purpose: "normal" | "diagnostic";
        capture_mode: "auto" | "skip";
        created_at: string;
        updated_at: string;
        asset: {
          id: string;
          kind: "uploaded_svg" | "built_in_pattern";
          pattern_id: string | null;
          name: string;
          timestamp: string;
          file_path: string;
          public_url: string;
          mime_type: string;
        };
        capture: typeof latestCapture;
        error: string | null;
        stage_states: Record<
          "prepare" | "plot" | "capture",
          {
            status: "pending" | "in_progress" | "completed";
            started_at: string | null;
            completed_at: string | null;
            message: string | null;
          }
        >;
        plotter_run_details: Record<string, unknown>;
        camera_run_details: Record<string, unknown>;
      };
  let recentRuns: Array<{
    id: string;
    status: "pending" | "plotting" | "capturing" | "completed";
    purpose: "normal" | "diagnostic";
    created_at: string;
    updated_at: string;
    asset_id: string;
    asset_name: string;
    asset_kind: "uploaded_svg" | "built_in_pattern";
    error: string | null;
  }>;
  let latestRunFetchCount: number;

  beforeEach(() => {
    latestCapture = null;
    latestRun = null;
    recentRuns = [];
    latestRunFetchCount = 0;

    vi.spyOn(globalThis, "fetch").mockImplementation(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        const patternAsset = {
          id: "asset-test-grid",
          kind: "built_in_pattern" as const,
          pattern_id: "test-grid",
          name: "Test grid",
          timestamp: "2026-03-15T20:04:00Z",
          file_path: "/tmp/asset-test-grid.svg",
          public_url: "/plot-assets/asset-test-grid.svg",
          mime_type: "image/svg+xml",
        };

        if (url === "/api/hardware/status") {
          return new Response(JSON.stringify(hardwareStatus), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/captures/latest") {
          return new Response(JSON.stringify({ capture: latestCapture }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plot-runs/latest") {
          if (latestRun && latestRun.status !== "completed") {
            latestRunFetchCount += 1;
            if (latestRunFetchCount === 1) {
              latestRun = {
                ...latestRun,
                status: "plotting",
                stage_states: {
                  ...latestRun.stage_states,
                  prepare: {
                    status: "completed",
                    started_at: "2026-03-15T20:04:01Z",
                    completed_at: "2026-03-15T20:04:01Z",
                    message: "SVG document prepared.",
                  },
                  plot: {
                    status: "in_progress",
                    started_at: "2026-03-15T20:04:02Z",
                    completed_at: null,
                    message: "Sending SVG to plotter.",
                  },
                },
              };
            } else if (latestRunFetchCount === 2) {
              latestRun = {
                ...latestRun,
                status: "capturing",
                stage_states: {
                  ...latestRun.stage_states,
                  plot: {
                    status: "completed",
                    started_at: "2026-03-15T20:04:02Z",
                    completed_at: "2026-03-15T20:04:03Z",
                    message: "Plot completed.",
                  },
                  capture: {
                    status: "in_progress",
                    started_at: "2026-03-15T20:04:04Z",
                    completed_at: null,
                    message: "Capturing plotted page.",
                  },
                },
              };
            } else {
              latestCapture = {
                id: "capture-run-001",
                timestamp: "2026-03-15T20:04:05Z",
                file_path: "/tmp/capture-run-001.svg",
                public_url: "/captures/capture-run-001.svg",
                width: 1280,
                height: 960,
                mime_type: "image/svg+xml",
              };
              latestRun = {
                ...latestRun,
                status: "completed",
                capture: latestCapture,
                stage_states: {
                  ...latestRun.stage_states,
                  capture: {
                    status: "completed",
                    started_at: "2026-03-15T20:04:04Z",
                    completed_at: "2026-03-15T20:04:05Z",
                    message: "Capture completed.",
                  },
                },
                camera_run_details: {
                  driver: "mock-camera",
                  capture_id: "capture-run-001",
                },
              };
              recentRuns = [
                {
                  id: latestRun.id,
                  status: "completed",
                  purpose: "normal",
                  created_at: latestRun.created_at,
                  updated_at: "2026-03-15T20:04:05Z",
                  asset_id: patternAsset.id,
                  asset_name: patternAsset.name,
                  asset_kind: patternAsset.kind,
                  error: null,
                },
              ];
            }
          }
          return new Response(JSON.stringify({ run: latestRun }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plot-runs") {
          if (method === "GET") {
            return new Response(JSON.stringify({ runs: recentRuns }), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            });
          }

          latestRunFetchCount = 0;
          latestRun = {
            id: "run-001",
            status: "pending",
            purpose: "normal",
            capture_mode: "auto",
            created_at: "2026-03-15T20:04:00Z",
            updated_at: "2026-03-15T20:04:00Z",
            asset: patternAsset,
            capture: null,
            error: null,
            stage_states: {
              prepare: {
                status: "in_progress",
                started_at: "2026-03-15T20:04:00Z",
                completed_at: null,
                message: "Preparing SVG document.",
              },
              plot: {
                status: "pending",
                started_at: null,
                completed_at: null,
                message: null,
              },
              capture: {
                status: "pending",
                started_at: null,
                completed_at: null,
                message: null,
              },
            },
            plotter_run_details: {},
            camera_run_details: {},
          };
          return new Response(JSON.stringify(latestRun), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plot-assets/patterns" && method === "POST") {
          return new Response(JSON.stringify(patternAsset), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/return-to-origin" && method === "POST") {
          return new Response(
            JSON.stringify({
              ok: true,
              message: "Plotter returned to origin.",
              status: hardwareStatus.plotter,
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          );
        }

        if (url === "/api/camera/capture" && method === "POST") {
          latestCapture = {
            id: "capture-001",
            timestamp: "2026-03-15T20:05:00Z",
            file_path: "/tmp/capture-001.svg",
            public_url: "/captures/capture-001.svg",
            width: 1280,
            height: 960,
            mime_type: "image/svg+xml",
          };
          return new Response(
            JSON.stringify({
              ok: true,
              message: "Image captured.",
              status: hardwareStatus.camera,
              capture: latestCapture,
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          );
        }

        return new Response("Not found", { status: 404 });
      },
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders current device state", async () => {
    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: /learntodraw local control panel/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/mock-plotter/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/mock-camera/i).length).toBeGreaterThan(0);
    expect(
      screen.getByText(/trigger a capture to save a local artifact/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/plot workflow/i)).toBeInTheDocument();
    expect(screen.getByText(/load test-grid/i)).toBeInTheDocument();
  });

  it("captures an image and refreshes the preview", async () => {
    render(<App />);

    const button = await screen.findByRole("button", {
      name: /capture image/i,
    });
    fireEvent.click(button);

    await waitFor(() => {
      expect(
        screen.getByRole("img", { name: /latest camera capture capture-001/i }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/image captured\./i)).toBeInTheDocument();
    expect(screen.getByText(/image\/svg\+xml/i)).toBeInTheDocument();
  });

  it("creates a built-in pattern and completes a plot run", async () => {
    render(<App />);

    fireEvent.click(
      await screen.findByRole("button", { name: /load test-grid/i }),
    );

    expect(
      await screen.findByText(/built-in test-grid pattern is ready to plot\./i),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: /start plot run/i,
      }),
    );

    expect(await screen.findByText(/plot run started\./i)).toBeInTheDocument();

    await waitFor(
      () => {
        expect(
          screen.getByRole("img", { name: /captured output for run run-001/i }),
        ).toBeInTheDocument();
      },
      { timeout: 5000 },
    );

    expect(screen.getAllByText(/test grid/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/completed/i).length).toBeGreaterThan(0);
  });

  it("updates axidraw pen heights from the hardware panel", async () => {
    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/hardware/status") {
          return new Response(JSON.stringify(axidrawHardwareStatus), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/captures/latest") {
          return new Response(JSON.stringify({ capture: null }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plot-runs/latest") {
          return new Response(JSON.stringify({ run: null }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plot-runs") {
          return new Response(JSON.stringify({ runs: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/pen-heights" && method === "POST") {
          const body = JSON.parse(String(init?.body ?? "{}"));
          axidrawHardwareStatus.plotter.details.pen_tuning.pen_pos_up = body.pen_pos_up;
          axidrawHardwareStatus.plotter.details.pen_tuning.pen_pos_down = body.pen_pos_down;
          return new Response(
            JSON.stringify({
              ok: true,
              message: "Plotter pen heights updated.",
              status: axidrawHardwareStatus.plotter,
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          );
        }

        return new Response("Not found", { status: 404 });
      },
    );

    render(<App />);

    const upInput = await screen.findByLabelText(/pen up/i);
    const downInput = screen.getByLabelText(/pen down/i);

    fireEvent.change(upInput, { target: { value: "66" } });
    fireEvent.change(downInput, { target: { value: "22" } });
    fireEvent.click(screen.getByRole("button", { name: /apply heights/i }));

    await waitFor(() => {
      expect(screen.getByText(/pen heights updated\./i)).toBeInTheDocument();
    });
  });
});
