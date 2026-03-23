import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { App } from "../src/app/App";
import {
  createHardwareDashboardHarness,
  defaultAxiDrawHardwareStatus,
  defaultCameraBridgeDetails,
  defaultCameraBridgeHardwareStatus,
  defaultDevice,
  defaultWorkspace,
  installHardwareDashboardFetchMock,
} from "./hardwareDashboardTestUtils";

describe("Hardware dashboard focused behaviors", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a backend-unavailable state when the api is unreachable on first load", async () => {
    const harness = createHardwareDashboardHarness({
      backendReachable: false,
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    expect(
      await screen.findByRole("heading", {
        name: /local backend unavailable/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/start the learntodraw api locally and retry/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows CameraBridge service guidance and disables capture while the service is offline", async () => {
    const harness = createHardwareDashboardHarness({
      currentHardwareStatus: {
        ...structuredClone(defaultAxiDrawHardwareStatus),
        camera: {
          ...structuredClone(defaultCameraBridgeHardwareStatus.camera),
          available: false,
          connected: false,
          details: {
            ...structuredClone(defaultCameraBridgeDetails),
            service_available: false,
            readiness_state: "needs_service",
            effective_selected_device_id: null,
            active_device_id: null,
            devices: [],
            device_count: 0,
          },
        },
      },
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    expect(
      await screen.findByRole("button", { name: /capture image/i }),
    ).toBeDisabled();
    expect(
      screen.getByText(/start camerabridge service/i),
    ).toBeInTheDocument();
  });

  it("shows guided CameraBridge permission messaging when permission is undecided", async () => {
    const harness = createHardwareDashboardHarness({
      currentHardwareStatus: {
        ...structuredClone(defaultAxiDrawHardwareStatus),
        camera: {
          ...structuredClone(defaultCameraBridgeHardwareStatus.camera),
          available: false,
          details: {
            ...structuredClone(defaultCameraBridgeDetails),
            permission_status: "not_determined",
            permission_message: "Open CameraBridgeApp to request camera access.",
            permission_next_step_kind: "open_camera_bridge_app",
            readiness_state: "needs_permission",
          },
        },
      },
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    expect(
      await screen.findAllByText(/open camerabridgeapp to request camera access/i),
    ).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: /capture image/i }),
    ).toBeDisabled();
  });

  it("persists CameraBridge device selection through the backend and enables capture", async () => {
    const harness = createHardwareDashboardHarness({
      currentHardwareStatus: {
        ...structuredClone(defaultAxiDrawHardwareStatus),
        camera: {
          ...structuredClone(defaultCameraBridgeHardwareStatus.camera),
          available: false,
          details: {
            ...structuredClone(defaultCameraBridgeDetails),
            devices: [
              {
                id: "camera-1",
                name: "Built-in Camera",
                position: "front",
              },
              {
                id: "camera-2",
                name: "Desk Camera",
                position: "external",
              },
            ],
            device_count: 2,
            active_device_id: null,
            effective_selected_device_id: null,
            persisted_selected_device_id: null,
            selection_required: true,
            readiness_state: "needs_device_selection",
          },
        },
      },
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);

    const select = await screen.findByLabelText(/choose a device/i);
    const captureButton = screen.getByRole("button", { name: /capture image/i });
    expect(captureButton).toBeDisabled();

    fireEvent.change(select, { target: { value: "camera-2" } });
    await waitFor(() => {
      expect(select).toHaveValue("camera-2");
    });
    fireEvent.click(screen.getByRole("button", { name: /save camera/i }));

    expect(await screen.findByText(/camera selection saved\./i)).toBeInTheDocument();
    expect(harness.cameraDeviceRequests).toEqual(["camera-2"]);

    await waitFor(() => {
      expect(captureButton).toBeEnabled();
    });
    expect(screen.getByText(/selected device: desk camera\./i)).toBeInTheDocument();
  });

  it("refreshes the latest capture preview after a successful CameraBridge capture", async () => {
    const harness = createHardwareDashboardHarness({
      currentHardwareStatus: {
        ...structuredClone(defaultAxiDrawHardwareStatus),
        camera: structuredClone(defaultCameraBridgeHardwareStatus.camera),
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

    expect(
      await screen.findByRole("heading", {
        name: /learntodraw local control panel/i,
      }),
    ).toBeInTheDocument();

    const paperCard = screen.getByText(/^paper on plotter$/i).closest(".workspace-card");
    expect(paperCard).not.toBeNull();

    const pageWidthInput = await within(paperCard as HTMLElement).findByLabelText(/^width$/i);
    const saveButton = within(paperCard as HTMLElement).getByRole("button", {
      name: /save paper setup/i,
    });

    await waitFor(() => {
      expect(pageWidthInput).toHaveValue(210);
      expect(saveButton).toBeDisabled();
    });

    fireEvent.change(pageWidthInput, { target: { value: "400" } });

    await waitFor(() => {
      expect(pageWidthInput).toHaveValue(400);
      expect(saveButton).toBeDisabled();
    });
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
