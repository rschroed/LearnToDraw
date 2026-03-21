import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { App } from "../src/app/App";
import {
  createHardwareDashboardHarness,
  defaultAxiDrawHardwareStatus,
  defaultDevice,
  defaultWorkspace,
  installHardwareDashboardFetchMock,
  makeHelperStatus,
} from "./hardwareDashboardTestUtils";

describe("Hardware dashboard focused behaviors", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("auto-starts the backend through the helper on first load", async () => {
    const harness = createHardwareDashboardHarness({
      backendReachable: false,
      helperReachable: true,
      helperStatus: makeHelperStatus({
        state: "stopped",
        backend_health: "unreachable",
      }),
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: /starting local camera backend/i,
      }),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByRole("heading", {
          name: /learntodraw local control panel/i,
        }),
      ).toBeInTheDocument();
    }, { timeout: 10000 });

    expect(harness.helperStartCount).toBe(1);
  }, 12000);

  it("shows a helper-missing startup state when the helper is unavailable", async () => {
    const harness = createHardwareDashboardHarness({
      backendReachable: false,
      helperReachable: false,
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: /local helper not running/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/open the learntodraw helper to bring localhost control online/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open helper/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("keeps capture enabled and shows actionable diagnostics after an opencv failure", async () => {
    const harness = createHardwareDashboardHarness({
      currentHardwareStatus: {
        ...structuredClone(defaultAxiDrawHardwareStatus),
        camera: {
          available: false,
          connected: false,
          busy: false,
          error: "OpenCV camera index 2 is unavailable or permission was denied.",
          driver: "opencv-camera",
          last_updated: "2026-03-15T20:00:00Z",
          details: {
            camera_index: 2,
            initialization_state: "unavailable",
            last_capture_id: null,
            resolution: null,
            last_action: "idle",
            last_open_result: "failed",
            last_open_message:
              "VideoCapture(2) did not open. macOS camera access may still be denied, the selected index may be wrong, or the device may be busy.",
            last_read_result: "not_attempted",
            last_backend_name: null,
          },
        },
      },
      cameraCaptureError: "OpenCV camera index 2 is unavailable or permission was denied.",
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    expect(
      await screen.findByRole("button", { name: /capture image/i }),
    ).toBeEnabled();
    expect(
      screen.getByText(/opencv could not open the selected camera\. camera index 2\./i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/check macos camera permission.*learn_to_draw_opencv_camera_index/i),
    ).toBeInTheDocument();
  });

  it("refreshes the latest capture preview after a successful real camera capture", async () => {
    const harness = createHardwareDashboardHarness({
      currentHardwareStatus: {
        ...structuredClone(defaultAxiDrawHardwareStatus),
        camera: {
          available: false,
          connected: false,
          busy: false,
          error: null,
          driver: "opencv-camera",
          last_updated: "2026-03-15T20:00:00Z",
          details: {
            camera_index: 0,
            initialization_state: "uninitialized",
            last_capture_id: null,
            resolution: null,
            last_action: "idle",
            last_open_result: "not_attempted",
            last_open_message: null,
            last_read_result: "not_attempted",
            last_backend_name: null,
          },
        },
      },
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /capture image/i }));

    expect(await screen.findByText(/image captured\./i)).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /latest camera capture capture-real-001/i }))
      .toBeInTheDocument();
    expect(screen.getByText(/1920 x 1080/i)).toBeInTheDocument();
    expect(screen.getByText(/image\/jpeg/i)).toBeInTheDocument();
    expect(harness.cameraCaptureAttempts).toBe(1);
  });

  it("keeps invalid paper setup drafts local and blocks save until they fit", async () => {
    const harness = createHardwareDashboardHarness();
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    const pageWidthInput = await screen.findByLabelText(/^width$/i);
    fireEvent.change(pageWidthInput, { target: { value: "400" } });

    await waitFor(() => {
      expect(
        screen.getAllByText(
          (_, element) =>
            element?.classList.contains("inline-notice-error") === true &&
            (element.textContent ?? "").includes(
              "Paper size exceeds the plotter's safe bounds of 210 x 297 mm.",
            ),
        ).length,
      ).toBeGreaterThan(0);
    });
    expect(screen.getByRole("button", { name: /save paper setup/i })).toBeDisabled();
    expect(harness.workspaceRequests).toHaveLength(0);
  });

  it("saves and resets operational safe bounds for axidraw", async () => {
    const harness = createHardwareDashboardHarness({
      currentHardwareStatus: structuredClone(defaultAxiDrawHardwareStatus),
      currentDevice: {
        ...structuredClone(defaultDevice),
        driver: "axidraw",
        plotter_model: {
          code: 1,
          label: "AxiDraw V3/A3",
        },
        nominal_plotter_bounds_mm: {
          width_mm: 300,
          height_mm: 218,
        },
        nominal_plotter_bounds_source: "model_default",
        plotter_bounds_mm: {
          width_mm: 290,
          height_mm: 208,
        },
        plotter_bounds_source: "default_clearance",
      },
      currentWorkspace: {
        ...structuredClone(defaultWorkspace),
        plotter_bounds_mm: {
          width_mm: 290,
          height_mm: 208,
        },
      },
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    const widthInputs = await screen.findAllByLabelText(/^width$/i);
    const heightInputs = await screen.findAllByLabelText(/^height$/i);

    fireEvent.change(widthInputs[0], {
      target: { value: "250" },
    });
    fireEvent.change(heightInputs[0], {
      target: { value: "180" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save safe bounds/i }));

    expect(await screen.findByText(/operational safe bounds updated\./i)).toBeInTheDocument();
    expect(harness.safeBoundsRequests[0]).toEqual({
      width_mm: 250,
      height_mm: 180,
    });

    fireEvent.click(screen.getByRole("button", { name: /reset to default clearance/i }));

    expect(await screen.findByText(/operational safe bounds reset\./i)).toBeInTheDocument();
    expect(harness.safeBoundsRequests[1]).toEqual({
      width_mm: null,
      height_mm: null,
    });
    expect(harness.currentDevice.plotter_bounds_mm).toEqual({
      width_mm: 290,
      height_mm: 208,
    });
  });

  it("dispatches plotter diagnostic actions through the backend", async () => {
    const harness = createHardwareDashboardHarness({
      currentHardwareStatus: structuredClone(defaultAxiDrawHardwareStatus),
      currentDevice: {
        ...structuredClone(defaultDevice),
        driver: "axidraw",
        plotter_model: {
          code: 1,
          label: "AxiDraw V3/A3",
        },
      },
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /disengage motors/i }));

    expect(await screen.findByText(/align completed\./i)).toBeInTheDocument();
    expect(harness.plotterTestActions).toEqual(["align"]);
  });
});
