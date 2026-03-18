import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

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
      plot_api_supported: false,
      manual_api_supported: true,
      config_source: "vendor_default",
      calibration_source: "vendor_default",
      native_res_factor: 1016,
      motion_scale: 1,
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

const defaultCalibration = {
  driver: "axidraw",
  motion_scale: 1,
  driver_calibration: {
    native_res_factor: 1016,
  },
  updated_at: "2026-03-15T20:00:00Z",
  source: "vendor_default" as const,
};

const defaultWorkspace = {
  plotter_bounds_mm: {
    width_mm: 210,
    height_mm: 297,
  },
  page_size_mm: {
    width_mm: 210,
    height_mm: 297,
  },
  margins_mm: {
    left_mm: 20,
    top_mm: 20,
    right_mm: 20,
    bottom_mm: 20,
  },
  drawable_area_mm: {
    width_mm: 170,
    height_mm: 257,
  },
  updated_at: "2026-03-15T20:00:00Z",
  source: "config_default" as const,
  is_valid: true,
  validation_error: null,
};

const defaultDevice = {
  driver: "mock",
  plotter_model: null,
  plotter_bounds_mm: {
    width_mm: 210,
    height_mm: 297,
  },
  plotter_bounds_source: "config_default" as const,
  updated_at: "2026-03-15T20:00:00Z",
  source: "config_default" as const,
};

type CalibrationFixture = {
  driver: string;
  motion_scale: number;
  driver_calibration: {
    native_res_factor: number;
  };
  updated_at: string;
  source: "vendor_default" | "persisted" | "env_override" | "explicit_path";
};

type WorkspaceFixture = {
  plotter_bounds_mm: {
    width_mm: number;
    height_mm: number;
  };
  page_size_mm: {
    width_mm: number;
    height_mm: number;
  };
  margins_mm: {
    left_mm: number;
    top_mm: number;
    right_mm: number;
    bottom_mm: number;
  };
  drawable_area_mm: {
    width_mm: number;
    height_mm: number;
  };
  updated_at: string;
  source: "config_default" | "persisted";
  is_valid: boolean;
  validation_error: string | null;
};

type DeviceFixture = {
  driver: string;
  plotter_model: {
    code: number;
    label: string;
  } | null;
  plotter_bounds_mm: {
    width_mm: number;
    height_mm: number;
  };
  plotter_bounds_source: "model_default" | "config_override" | "config_default";
  updated_at: string;
  source: "config_default" | "persisted";
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
  let currentCalibration: CalibrationFixture;
  let currentDevice: DeviceFixture;
  let currentWorkspace: WorkspaceFixture;

  beforeEach(() => {
    latestCapture = null;
    latestRun = null;
    recentRuns = [];
    latestRunFetchCount = 0;
    currentCalibration = structuredClone(defaultCalibration);
    currentDevice = structuredClone(defaultDevice);
    currentWorkspace = structuredClone(defaultWorkspace);

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

        if (url === "/api/plotter/calibration") {
          if (method === "POST") {
            const body = JSON.parse(String(init?.body ?? "{}"));
            currentCalibration = {
              ...currentCalibration,
              motion_scale: Number((body.native_res_factor / 1016).toFixed(6)),
              driver_calibration: {
                native_res_factor: body.native_res_factor,
              },
              updated_at: "2026-03-15T20:00:10Z",
              source: "persisted",
            };
            return new Response(
              JSON.stringify({
                ok: true,
                message: "Plotter calibration updated.",
                calibration: currentCalibration,
              }),
              {
                status: 200,
                headers: { "Content-Type": "application/json" },
              },
            );
          }

          return new Response(JSON.stringify(currentCalibration), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/device") {
          return new Response(JSON.stringify(currentDevice), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/workspace") {
          if (method === "POST") {
            const body = JSON.parse(String(init?.body ?? "{}"));
            currentWorkspace = {
              ...currentWorkspace,
              page_size_mm: {
                width_mm: body.page_width_mm,
                height_mm: body.page_height_mm,
              },
              margins_mm: {
                left_mm: body.margin_left_mm,
                top_mm: body.margin_top_mm,
                right_mm: body.margin_right_mm,
                bottom_mm: body.margin_bottom_mm,
              },
              drawable_area_mm: {
                width_mm: body.page_width_mm - body.margin_left_mm - body.margin_right_mm,
                height_mm: body.page_height_mm - body.margin_top_mm - body.margin_bottom_mm,
              },
              updated_at: "2026-03-15T20:00:12Z",
              source: "persisted",
              is_valid: true,
              validation_error: null,
            };
            return new Response(
              JSON.stringify({
                ok: true,
                message: "Plotter workspace updated.",
                workspace: currentWorkspace,
              }),
              {
                status: 200,
                headers: { "Content-Type": "application/json" },
              },
            );
          }

          return new Response(JSON.stringify(currentWorkspace), {
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
            plotter_run_details: {
              preparation: {
                source_width: 160,
                source_height: 120,
                source_units: "mm",
                prepared_width_mm: 160,
                prepared_height_mm: 120,
                page_width_mm: 210,
                page_height_mm: 297,
                drawable_width_mm: 170,
                drawable_height_mm: 257,
                plotter_bounds_width_mm: 210,
                plotter_bounds_height_mm: 297,
                plotter_bounds_source: "config_default",
                units_inferred: false,
                workspace_audit: {
                  page_within_plotter_bounds: true,
                  drawable_area_positive: true,
                  drawable_origin_x_mm: 20,
                  drawable_origin_y_mm: 20,
                  remaining_bounds_right_mm: 0,
                  remaining_bounds_bottom_mm: 0,
                },
                preparation_audit: {
                  strategy: "fit_top_left",
                  fit_scale: 0.166667,
                  prepared_within_drawable_area: true,
                  overflow_x_mm: 0,
                  overflow_y_mm: 0,
                  placement_origin_x_mm: 20,
                  placement_origin_y_mm: 20,
                  content_min_x_mm: 20,
                  content_min_y_mm: 20,
                  content_max_x_mm: 180,
                  content_max_y_mm: 140,
                  content_width_mm: 160,
                  content_height_mm: 120,
                  prepared_viewbox_min_x: null,
                  prepared_viewbox_min_y: null,
                  prepared_viewbox_width: 210,
                  prepared_viewbox_height: 297,
                },
              },
            },
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

        if (url === "/api/plotter/walk-home" && method === "POST") {
          return new Response(
            JSON.stringify({
              ok: true,
              message: "Plotter walked home.",
              status: hardwareStatus.plotter,
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          );
        }

        if (url === "/api/plotter/test-actions" && method === "POST") {
          const body = JSON.parse(String(init?.body ?? "{}"));
          return new Response(
            JSON.stringify({
              ok: true,
              message: `Plotter test action '${body.action}' completed.`,
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
    vi.useRealTimers();
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
    expect(
      screen.getByText(/normal plots are prepared automatically into the drawable area/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/^paper setup$/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /^preview$/i })).toBeInTheDocument();
    expect(screen.getByText(/safe plotter bounds/i)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /paper setup preview/i })).toBeInTheDocument();
    expect(screen.getByText(/paper 210 x 297 mm/i)).toBeInTheDocument();
  });

  it("shows a disengage motors button for axidraw and runs align mode", async () => {
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

        if (url === "/api/plotter/calibration") {
          return new Response(JSON.stringify(currentCalibration), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/device") {
          return new Response(JSON.stringify(currentDevice), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/workspace") {
          return new Response(JSON.stringify(currentWorkspace), {
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

        if (url === "/api/plot-runs" && method === "GET") {
          return new Response(JSON.stringify({ runs: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/test-actions" && method === "POST") {
          const body = JSON.parse(String(init?.body ?? "{}"));
          return new Response(
            JSON.stringify({
              ok: true,
              message: `Plotter test action '${body.action}' completed.`,
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

    fireEvent.click(
      await screen.findByRole("button", { name: /disengage motors/i }),
    );

    expect(await screen.findByText(/^align completed\.$/i)).toBeInTheDocument();
  });

  it("updates the drawable area summary while paper setup is being edited", async () => {
    render(<App />);

    fireEvent.change(await screen.findByLabelText(/^width$/i), {
      target: { value: "200" },
    });
    fireEvent.change(screen.getByLabelText(/^top$/i), {
      target: { value: "25" },
    });

    expect(screen.getByText("160 mm x 252 mm")).toBeInTheDocument();
  });

  it("keeps an invalid saved paper setup readable while blocking plotting", async () => {
    vi.restoreAllMocks();
    currentDevice = {
      ...currentDevice,
      driver: "axidraw",
      plotter_bounds_mm: {
        width_mm: 300,
        height_mm: 218,
      },
      plotter_bounds_source: "config_override",
    };
    currentWorkspace = {
      ...currentWorkspace,
      plotter_bounds_mm: {
        width_mm: 300,
        height_mm: 218,
      },
      is_valid: false,
      validation_error: "Configured page height exceeds the plotter bounds height.",
    };

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

        if (url === "/api/plotter/calibration") {
          return new Response(JSON.stringify(currentCalibration), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/device") {
          return new Response(JSON.stringify(currentDevice), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/workspace") {
          return new Response(JSON.stringify(currentWorkspace), {
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

        if (url === "/api/plot-runs" && method === "GET") {
          return new Response(JSON.stringify({ runs: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        return new Response("Not found", { status: 404 });
      },
    );

    render(<App />);

    expect(
      await screen.findByText(
        /saved paper setup is invalid for the current machine bounds/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/plotting is blocked until paper setup fits the current machine bounds/i),
    ).toBeInTheDocument();
    expect(
      screen.getAllByText(/configured page height exceeds the plotter bounds height\./i),
    ).toHaveLength(2);
    expect(screen.getByRole("button", { name: /tiny square/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /start plot run/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /save paper setup/i })).toBeDisabled();
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
      await screen.findByText(
        /built-in test-grid pattern is ready to plot with automatic drawable-area preparation\./i,
      ),
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
    expect(screen.getByText(/math audit: math audit ok/i)).toBeInTheDocument();
    expect(screen.getByText(/plotter bounds: 210 × 297 mm/i)).toBeInTheDocument();
    expect(
      screen.getByText(/workspace: page 210 × 297 mm · drawable 170 × 257 mm/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/workspace audit: origin 20 × 20 mm · remaining bounds 0 × 0 mm/i)).toBeInTheDocument();
  });

  it("shows fit preparation audit details for the latest run", async () => {
    latestRun = {
      id: "run-fit-001",
      status: "completed",
      purpose: "normal",
      capture_mode: "skip",
      created_at: "2026-03-15T20:06:00Z",
      updated_at: "2026-03-15T20:06:05Z",
      asset: {
        id: "asset-fit-001",
        kind: "uploaded_svg",
        pattern_id: null,
        name: "Unitless upload",
        timestamp: "2026-03-15T20:06:00Z",
        file_path: "/tmp/unitless-upload.svg",
        public_url: "/plot-assets/unitless-upload.svg",
        mime_type: "image/svg+xml",
      },
      capture: null,
      error: null,
      stage_states: {
        prepare: {
          status: "completed",
          started_at: "2026-03-15T20:06:00Z",
          completed_at: "2026-03-15T20:06:01Z",
          message: "SVG document prepared.",
        },
        plot: {
          status: "completed",
          started_at: "2026-03-15T20:06:02Z",
          completed_at: "2026-03-15T20:06:03Z",
          message: "Plot completed.",
        },
        capture: {
          status: "completed",
          started_at: null,
          completed_at: null,
          message: "Capture skipped for diagnostic run.",
        },
      },
      plotter_run_details: {
        preparation: {
          source_width: 200,
          source_height: 100,
          source_units: "unitless",
          prepared_width_mm: 170,
          prepared_height_mm: 85,
          page_width_mm: 210,
          page_height_mm: 297,
          drawable_width_mm: 170,
          drawable_height_mm: 257,
          plotter_bounds_width_mm: 210,
          plotter_bounds_height_mm: 297,
          plotter_bounds_source: "config_default",
          units_inferred: true,
          workspace_audit: {
            page_within_plotter_bounds: true,
            drawable_area_positive: true,
            drawable_origin_x_mm: 20,
            drawable_origin_y_mm: 20,
            remaining_bounds_right_mm: 0,
            remaining_bounds_bottom_mm: 0,
          },
          preparation_audit: {
            strategy: "fit_top_left",
            fit_scale: 0.85,
            prepared_within_drawable_area: true,
            overflow_x_mm: 0,
            overflow_y_mm: 0,
            placement_origin_x_mm: 20,
            placement_origin_y_mm: 20,
            content_min_x_mm: 20,
            content_min_y_mm: 20,
            content_max_x_mm: 190,
            content_max_y_mm: 105,
            content_width_mm: 170,
            content_height_mm: 85,
            prepared_viewbox_min_x: 0,
            prepared_viewbox_min_y: 0,
            prepared_viewbox_width: 210,
            prepared_viewbox_height: 297,
          },
        },
      },
      camera_run_details: {
        capture_mode: "skip",
      },
    };

    render(<App />);

    expect(await screen.findByText(/math audit: math audit ok/i)).toBeInTheDocument();
    expect(screen.getByText(/preparation strategy: fit top left/i)).toBeInTheDocument();
    expect(screen.getByText(/fit scale: 0.85/i)).toBeInTheDocument();
    expect(
      screen.getByText(/prepared placement: origin 20 × 20 mm · content box 20 20 → 190 105 mm/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/prepared root viewbox: 0 0 210 297/i),
    ).toBeInTheDocument();
  });

  it("prepares uploaded SVGs automatically without a sizing selector", async () => {
    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        const uploadedAsset = {
          id: "asset-upload-001",
          kind: "uploaded_svg" as const,
          pattern_id: null,
          name: "Unitless upload",
          timestamp: "2026-03-15T20:06:00Z",
          file_path: "/tmp/unitless-upload.svg",
          public_url: "/plot-assets/unitless-upload.svg",
          mime_type: "image/svg+xml",
        };

        if (url === "/api/hardware/status") {
          return new Response(JSON.stringify(hardwareStatus), {
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

        if (url === "/api/plotter/workspace") {
          return new Response(JSON.stringify(currentWorkspace), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/calibration") {
          return new Response(JSON.stringify(currentCalibration), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/device") {
          return new Response(JSON.stringify(currentDevice), {
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

        if (url === "/api/plot-runs" && method === "GET") {
          return new Response(JSON.stringify({ runs: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plot-assets/upload" && method === "POST") {
          return new Response(JSON.stringify(uploadedAsset), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        return new Response("Not found", { status: 404 });
      },
    );

    render(<App />);

    const fileInput = (await screen.findByLabelText(/upload svg/i)) as HTMLInputElement;
    const file = new File(
      ["<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100' viewBox='0 0 200 100' />"],
      "unitless.svg",
      { type: "image/svg+xml" },
    );

    fireEvent.change(fileInput, { target: { files: [file] } });

    expect(
      await screen.findByText(
        /uploaded svgs are prepared automatically into the current drawable area\./i,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/plot sizing/i)).not.toBeInTheDocument();
  });

  it("allows real axidraw uploads without a fit-mode block", async () => {
    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        const uploadedAsset = {
          id: "asset-upload-axidraw-001",
          kind: "uploaded_svg" as const,
          pattern_id: null,
          name: "Unitless upload",
          timestamp: "2026-03-15T20:06:00Z",
          file_path: "/tmp/unitless-upload.svg",
          public_url: "/plot-assets/unitless-upload.svg",
          mime_type: "image/svg+xml",
        };

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

        if (url === "/api/plotter/workspace") {
          return new Response(JSON.stringify(currentWorkspace), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/calibration") {
          return new Response(JSON.stringify(currentCalibration), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/device") {
          return new Response(JSON.stringify(currentDevice), {
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

        if (url === "/api/plot-runs" && method === "GET") {
          return new Response(JSON.stringify({ runs: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plot-assets/upload" && method === "POST") {
          return new Response(JSON.stringify(uploadedAsset), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        return new Response("Not found", { status: 404 });
      },
    );

    render(<App />);

    const fileInput = (await screen.findByLabelText(/upload svg/i)) as HTMLInputElement;
    const file = new File(
      ["<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100' viewBox='0 0 200 100' />"],
      "unitless.svg",
      { type: "image/svg+xml" },
    );

    fireEvent.change(fileInput, { target: { files: [file] } });

    expect(
      await screen.findByText(
        /uploaded svgs are prepared automatically into the current drawable area\./i,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/plot sizing/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start plot run/i })).toBeEnabled();
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

        if (url === "/api/plotter/workspace") {
          return new Response(JSON.stringify(currentWorkspace), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/calibration") {
          return new Response(JSON.stringify(currentCalibration), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/device") {
          return new Response(JSON.stringify(currentDevice), {
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

    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 2600));
    });

    expect(screen.getByLabelText(/pen up/i)).toHaveValue(66);
    expect(screen.getByLabelText(/pen down/i)).toHaveValue(22);

    fireEvent.click(screen.getByRole("button", { name: /apply heights/i }));

    await waitFor(() => {
      expect(screen.getByText(/pen heights updated\./i)).toBeInTheDocument();
    }, { timeout: 8000 });

    await waitFor(() => {
      expect(screen.getByLabelText(/pen up/i)).toHaveValue(66);
      expect(screen.getByLabelText(/pen down/i)).toHaveValue(22);
    });

  }, 10000);

  it("blocks invalid pen heights before the request is sent", async () => {
    vi.restoreAllMocks();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(
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

        if (url === "/api/plotter/workspace") {
          if (method === "POST") {
            const body = JSON.parse(String(init?.body ?? "{}"));
            currentWorkspace = {
              ...currentWorkspace,
              page_size_mm: {
                width_mm: body.page_width_mm,
                height_mm: body.page_height_mm,
              },
              margins_mm: {
                left_mm: body.margin_left_mm,
                top_mm: body.margin_top_mm,
                right_mm: body.margin_right_mm,
                bottom_mm: body.margin_bottom_mm,
              },
              drawable_area_mm: {
                width_mm: body.page_width_mm - body.margin_left_mm - body.margin_right_mm,
                height_mm: body.page_height_mm - body.margin_top_mm - body.margin_bottom_mm,
              },
              updated_at: "2026-03-15T20:00:15Z",
              source: "persisted",
              is_valid: true,
              validation_error: null,
            };
            return new Response(
              JSON.stringify({
                ok: true,
                message: "Plotter workspace updated.",
                workspace: currentWorkspace,
              }),
              {
                status: 200,
                headers: { "Content-Type": "application/json" },
              },
            );
          }

          return new Response(JSON.stringify(currentWorkspace), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/calibration") {
          return new Response(JSON.stringify(currentCalibration), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/device") {
          return new Response(JSON.stringify(currentDevice), {
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
          return new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        return new Response("Not found", { status: 404 });
      },
    );

    render(<App />);

    const upInput = await screen.findByLabelText(/pen up/i);
    const downInput = screen.getByLabelText(/pen down/i);
    const applyButton = screen.getByRole("button", { name: /apply heights/i });

    fireEvent.change(upInput, { target: { value: "20" } });
    fireEvent.change(downInput, { target: { value: "20" } });

    expect(
      screen.getByText(/pen down must be lower than pen up\./i),
    ).toBeInTheDocument();
    expect(applyButton).toBeDisabled();

    fireEvent.change(upInput, { target: { value: "101" } });
    fireEvent.change(downInput, { target: { value: "10" } });

    expect(
      screen.getByText(/pen heights must stay between 0 and 100\./i),
    ).toBeInTheDocument();
    expect(applyButton).toBeDisabled();

    expect(
      fetchSpy.mock.calls.some(([url]) => String(url) === "/api/plotter/pen-heights"),
    ).toBe(false);
  });

  it("saves persisted calibration from the hardware panel", async () => {
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

        if (url === "/api/plotter/workspace") {
          return new Response(JSON.stringify(currentWorkspace), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/calibration") {
          if (method === "POST") {
            const body = JSON.parse(String(init?.body ?? "{}"));
            currentCalibration = {
              ...currentCalibration,
              motion_scale: Number((body.native_res_factor / 1016).toFixed(6)),
              driver_calibration: {
                native_res_factor: body.native_res_factor,
              },
              updated_at: "2026-03-15T20:00:15Z",
              source: "persisted",
            };
            axidrawHardwareStatus.plotter.details.native_res_factor = body.native_res_factor;
            axidrawHardwareStatus.plotter.details.motion_scale = currentCalibration.motion_scale;
            axidrawHardwareStatus.plotter.details.calibration_source = "persisted";
            return new Response(
              JSON.stringify({
                ok: true,
                message: "Plotter calibration updated.",
                calibration: currentCalibration,
              }),
              {
                status: 200,
                headers: { "Content-Type": "application/json" },
              },
            );
          }

          return new Response(JSON.stringify(currentCalibration), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/device") {
          return new Response(JSON.stringify(currentDevice), {
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

        if (url === "/api/plot-runs" && method === "GET") {
          return new Response(JSON.stringify({ runs: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        return new Response("Not found", { status: 404 });
      },
    );

    render(<App />);

    const input = await screen.findByLabelText(/native res factor/i);
    fireEvent.change(input, { target: { value: "1905" } });
    fireEvent.click(screen.getByRole("button", { name: /save calibration/i }));

    await waitFor(() => {
      expect(screen.getByText(/plotter calibration saved\./i)).toBeInTheDocument();
    });
    expect(screen.getByText(/^Motion scale$/i)).toBeInTheDocument();
    expect(screen.getByText("1.875000")).toBeInTheDocument();
    expect(screen.getByText(/^Calibration source$/i)).toBeInTheDocument();
    expect(screen.getAllByText(/^persisted$/i).length).toBeGreaterThan(0);
  });

  it("saves session paper setup from the hardware panel", async () => {
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

        if (url === "/api/plotter/workspace") {
          if (method === "POST") {
            const body = JSON.parse(String(init?.body ?? "{}"));
            currentWorkspace = {
              ...currentWorkspace,
              page_size_mm: {
                width_mm: body.page_width_mm,
                height_mm: body.page_height_mm,
              },
              margins_mm: {
                left_mm: body.margin_left_mm,
                top_mm: body.margin_top_mm,
                right_mm: body.margin_right_mm,
                bottom_mm: body.margin_bottom_mm,
              },
              drawable_area_mm: {
                width_mm: body.page_width_mm - body.margin_left_mm - body.margin_right_mm,
                height_mm: body.page_height_mm - body.margin_top_mm - body.margin_bottom_mm,
              },
              updated_at: "2026-03-15T20:00:18Z",
              source: "persisted",
              is_valid: true,
              validation_error: null,
            };
            return new Response(
              JSON.stringify({
                ok: true,
                message: "Plotter workspace updated.",
                workspace: currentWorkspace,
              }),
              {
                status: 200,
                headers: { "Content-Type": "application/json" },
              },
            );
          }

          return new Response(JSON.stringify(currentWorkspace), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/calibration") {
          return new Response(JSON.stringify(currentCalibration), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/device") {
          return new Response(JSON.stringify(currentDevice), {
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

        if (url === "/api/plot-runs" && method === "GET") {
          return new Response(JSON.stringify({ runs: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        return new Response("Not found", { status: 404 });
      },
    );

    render(<App />);

    fireEvent.change(await screen.findByLabelText(/^width$/i), {
      target: { value: "148" },
    });
    fireEvent.change(screen.getByLabelText(/^height$/i), {
      target: { value: "210" },
    });
    fireEvent.change(screen.getByLabelText(/^left$/i), {
      target: { value: "10" },
    });
    fireEvent.change(screen.getByLabelText(/^top$/i), {
      target: { value: "10" },
    });
    fireEvent.change(screen.getByLabelText(/^right$/i), {
      target: { value: "10" },
    });
    fireEvent.change(screen.getByLabelText(/^bottom$/i), {
      target: { value: "10" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save paper setup/i }));

    await waitFor(() => {
      expect(screen.getByText(/plotter workspace saved\./i)).toBeInTheDocument();
    });
    expect(screen.getByText("128 mm x 190 mm")).toBeInTheDocument();
  });

  it("shows a readiness notice when official plot support is unavailable", async () => {
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

        if (url === "/api/plotter/workspace") {
          return new Response(JSON.stringify(currentWorkspace), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/calibration") {
          return new Response(JSON.stringify(currentCalibration), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/device") {
          return new Response(JSON.stringify(currentDevice), {
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

        if (url === "/api/plot-runs" && method === "GET") {
          return new Response(JSON.stringify({ runs: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        return new Response("Not found", { status: 404 });
      },
    );

    render(<App />);

    expect(
      await screen.findByText(/trusted svg plotting is disabled until the official pyaxidraw plot api is installed/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/^Plot API support$/i)).toBeInTheDocument();
    expect(screen.getByText(/^Manual API support$/i)).toBeInTheDocument();
  });

  it("shows skip-capture messaging for diagnostic runs", async () => {
    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        const diagnosticAsset = {
          id: "asset-dash-row",
          kind: "built_in_pattern" as const,
          pattern_id: "dash-row",
          name: "Dash row",
          timestamp: "2026-03-15T20:10:00Z",
          file_path: "/tmp/asset-dash-row.svg",
          public_url: "/plot-assets/asset-dash-row.svg",
          mime_type: "image/svg+xml",
        };
        const diagnosticRun = {
          id: "run-diagnostic-001",
          status: "completed" as const,
          purpose: "diagnostic" as const,
          capture_mode: "skip" as const,
          created_at: "2026-03-15T20:10:00Z",
          updated_at: "2026-03-15T20:10:10Z",
          asset: diagnosticAsset,
          capture: null,
          error: null,
          stage_states: {
            prepare: {
              status: "completed" as const,
              started_at: "2026-03-15T20:10:00Z",
              completed_at: "2026-03-15T20:10:01Z",
              message: "Prepared diagnostic pattern.",
            },
            plot: {
              status: "completed" as const,
              started_at: "2026-03-15T20:10:02Z",
              completed_at: "2026-03-15T20:10:05Z",
              message: "Diagnostic plot completed.",
            },
            capture: {
              status: "completed" as const,
              started_at: null,
              completed_at: null,
              message: "Capture skipped.",
            },
          },
          plotter_run_details: {
            preparation: {
              source_width: 40,
              source_height: 12,
              source_units: "mm",
              prepared_width_mm: 40,
              prepared_height_mm: 12,
              page_width_mm: 210,
              page_height_mm: 297,
              drawable_width_mm: 170,
              drawable_height_mm: 257,
              plotter_bounds_width_mm: 210,
              plotter_bounds_height_mm: 297,
              plotter_bounds_source: "config_default",
              units_inferred: false,
              workspace_audit: {
                page_within_plotter_bounds: true,
                drawable_area_positive: true,
                drawable_origin_x_mm: 20,
                drawable_origin_y_mm: 20,
                remaining_bounds_right_mm: 0,
                remaining_bounds_bottom_mm: 0,
              },
              preparation_audit: {
                strategy: "diagnostic_passthrough",
                fit_scale: null,
                prepared_within_drawable_area: true,
                overflow_x_mm: 0,
                overflow_y_mm: 0,
                placement_origin_x_mm: 0,
                placement_origin_y_mm: 0,
                content_min_x_mm: 0,
                content_min_y_mm: 0,
                content_max_x_mm: 40,
                content_max_y_mm: 12,
                content_width_mm: 40,
                content_height_mm: 12,
                prepared_viewbox_min_x: null,
                prepared_viewbox_min_y: null,
                prepared_viewbox_width: null,
                prepared_viewbox_height: null,
              },
            },
          },
          camera_run_details: {},
        };

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

        if (url === "/api/plotter/workspace") {
          return new Response(JSON.stringify(currentWorkspace), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/calibration") {
          return new Response(JSON.stringify(currentCalibration), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/device") {
          return new Response(JSON.stringify(currentDevice), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plot-runs/latest") {
          return new Response(JSON.stringify({ run: diagnosticRun }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plot-runs" && method === "GET") {
          return new Response(
            JSON.stringify({
              runs: [
                {
                  id: diagnosticRun.id,
                  status: diagnosticRun.status,
                  purpose: diagnosticRun.purpose,
                  created_at: diagnosticRun.created_at,
                  updated_at: diagnosticRun.updated_at,
                  asset_id: diagnosticAsset.id,
                  asset_name: diagnosticAsset.name,
                  asset_kind: diagnosticAsset.kind,
                  error: null,
                },
              ],
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

    expect(
      await screen.findByText(/capture was skipped for this diagnostic run\./i),
    ).toBeInTheDocument();
    expect(screen.getByText(/run run-diag.*capture skipped/i)).toBeInTheDocument();
  });

  it("preserves a manual staged asset across refreshes and flags when latest run differs", async () => {
    vi.restoreAllMocks();
    const manualAsset = {
      id: "asset-test-grid",
      kind: "built_in_pattern" as const,
      pattern_id: "test-grid",
      name: "Test grid",
      timestamp: "2026-03-15T20:04:00Z",
      file_path: "/tmp/asset-test-grid.svg",
      public_url: "/plot-assets/asset-test-grid.svg",
      mime_type: "image/svg+xml",
    };
    const externalAsset = {
      id: "asset-double-box",
      kind: "built_in_pattern" as const,
      pattern_id: "double-box",
      name: "Double box",
      timestamp: "2026-03-15T20:12:00Z",
      file_path: "/tmp/asset-double-box.svg",
      public_url: "/plot-assets/asset-double-box.svg",
      mime_type: "image/svg+xml",
    };
    let latestRunResponse: null | {
      id: string;
      status: "completed";
      purpose: "diagnostic";
      capture_mode: "skip";
      created_at: string;
      updated_at: string;
      asset: typeof externalAsset;
      capture: null;
      error: null;
      stage_states: {
        prepare: {
          status: "completed";
          started_at: string;
          completed_at: string;
          message: string;
        };
        plot: {
          status: "completed";
          started_at: string;
          completed_at: string;
          message: string;
        };
        capture: {
          status: "completed";
          started_at: null;
          completed_at: null;
          message: string;
        };
      };
      plotter_run_details: Record<string, unknown>;
      camera_run_details: Record<string, unknown>;
    } = null;

    vi.spyOn(globalThis, "fetch").mockImplementation(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/hardware/status") {
          return new Response(JSON.stringify(hardwareStatus), {
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

        if (url === "/api/plotter/calibration") {
          return new Response(JSON.stringify(currentCalibration), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/device") {
          return new Response(JSON.stringify(currentDevice), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plotter/workspace") {
          return new Response(JSON.stringify(currentWorkspace), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plot-assets/patterns" && method === "POST") {
          return new Response(JSON.stringify(manualAsset), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plot-runs/latest") {
          return new Response(JSON.stringify({ run: latestRunResponse }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        if (url === "/api/plot-runs" && method === "GET") {
          return new Response(JSON.stringify({ runs: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }

        return new Response("Not found", { status: 404 });
      },
    );

    render(<App />);

    fireEvent.click(
      await screen.findByRole("button", { name: /load test-grid/i }),
    );

    expect(
      await screen.findByText(/staged source: test grid/i),
    ).toBeInTheDocument();

    latestRunResponse = {
      id: "run-diagnostic-002",
      status: "completed",
      purpose: "diagnostic",
      capture_mode: "skip",
      created_at: "2026-03-15T20:12:00Z",
      updated_at: "2026-03-15T20:12:05Z",
      asset: externalAsset,
      capture: null,
      error: null,
      stage_states: {
        prepare: {
          status: "completed",
          started_at: "2026-03-15T20:12:00Z",
          completed_at: "2026-03-15T20:12:01Z",
          message: "Prepared external run.",
        },
        plot: {
          status: "completed",
          started_at: "2026-03-15T20:12:02Z",
          completed_at: "2026-03-15T20:12:05Z",
          message: "External run completed.",
        },
        capture: {
          status: "completed",
          started_at: null,
          completed_at: null,
          message: "Capture skipped.",
        },
      },
      plotter_run_details: {
        preparation: {
          source_width: 40,
          source_height: 20,
          source_units: "mm",
          prepared_width_mm: 40,
          prepared_height_mm: 20,
          page_width_mm: 210,
          page_height_mm: 297,
          drawable_width_mm: 170,
          drawable_height_mm: 257,
          plotter_bounds_width_mm: 210,
          plotter_bounds_height_mm: 297,
          plotter_bounds_source: "config_default",
          units_inferred: false,
          workspace_audit: {
            page_within_plotter_bounds: true,
            drawable_area_positive: true,
            drawable_origin_x_mm: 20,
            drawable_origin_y_mm: 20,
            remaining_bounds_right_mm: 0,
            remaining_bounds_bottom_mm: 0,
          },
          preparation_audit: {
            strategy: "diagnostic_passthrough",
            fit_scale: null,
            prepared_within_drawable_area: true,
            overflow_x_mm: 0,
            overflow_y_mm: 0,
            placement_origin_x_mm: 0,
            placement_origin_y_mm: 0,
            content_min_x_mm: 0,
            content_min_y_mm: 0,
            content_max_x_mm: 40,
            content_max_y_mm: 20,
            content_width_mm: 40,
            content_height_mm: 20,
            prepared_viewbox_min_x: null,
            prepared_viewbox_min_y: null,
            prepared_viewbox_width: null,
            prepared_viewbox_height: null,
          },
        },
      },
      camera_run_details: {},
    };

    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 3600));
    });

    expect(screen.getByText(/staged source: test grid/i)).toBeInTheDocument();
    expect(
      screen.getByText(/latest run used a different source: double box\./i),
    ).toBeInTheDocument();

  }, 10000);
});
