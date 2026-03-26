import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import { App } from "../src/app/App";
import { CameraPanel } from "../src/features/hardware/CameraPanel";
import * as api from "../src/lib/api";
import {
  createHardwareDashboardHarness,
  defaultAxiDrawHardwareStatus,
  defaultCameraBridgeDetails,
  defaultCameraBridgeHardwareStatus,
  defaultDevice,
  installHardwareDashboardFetchMock,
} from "./hardwareDashboardTestUtils";

describe("machine and camera focused behaviors", () => {
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
  });

  it("shows CameraBridge service guidance on the Machine tab when the service is offline", async () => {
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
    fireEvent.click(await screen.findByRole("button", { name: /^machine$/i }));

    expect(
      await screen.findByRole("button", { name: /capture test image/i }),
    ).toBeDisabled();
    expect(screen.getAllByText(/start camerabridge/i).length).toBeGreaterThan(0);
    expect(
      screen.getByRole("button", { name: /open camerabridgeapp/i }),
    ).toBeInTheDocument();
  });

  it("opens CameraBridgeApp from the offline handoff button", async () => {
    const openCameraBridgeAppSpy = vi
      .spyOn(api, "openCameraBridgeApp")
      .mockImplementation(() => {});

    render(
      <CameraPanel
        cameraStatus={{
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
        }}
        actionName={null}
        actionFeedback={null}
        capture={async () => {}}
        setCameraDevice={async () => {}}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: /open camerabridgeapp/i }),
    );

    expect(openCameraBridgeAppSpy).toHaveBeenCalledTimes(1);
  });

  it("persists CameraBridge device selection through the backend on the Machine tab", async () => {
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
    fireEvent.click(await screen.findByRole("button", { name: /^machine$/i }));

    const select = await screen.findByLabelText(/choose camera/i);
    fireEvent.change(select, { target: { value: "camera-2" } });
    fireEvent.click(screen.getByRole("button", { name: /save camera/i }));

    expect(await screen.findByText(/camera selection saved\./i)).toBeInTheDocument();
    expect(harness.cameraDeviceRequests).toEqual(["camera-2"]);
    const cameraPanel = screen.getByRole("heading", { name: /^camera$/i }).closest(".machine-camera-panel");
    expect(cameraPanel).not.toBeNull();
    expect(
      within(cameraPanel as HTMLElement).getByRole("heading", { name: /^desk camera$/i, level: 3 }),
    ).toBeInTheDocument();
  });

  it("refreshes the saved capture after a successful Machine-tab capture", async () => {
    const harness = createHardwareDashboardHarness({
      currentHardwareStatus: {
        ...structuredClone(defaultAxiDrawHardwareStatus),
        camera: structuredClone(defaultCameraBridgeHardwareStatus.camera),
      },
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /^machine$/i }));
    fireEvent.click(await screen.findByRole("button", { name: /capture test image/i }));

    expect(await screen.findByText(/image captured\./i)).toBeInTheDocument();
    expect(screen.queryByText(/latest capture/i)).not.toBeInTheDocument();
  });

  it("keeps invalid paper setup drafts local and blocks save until they fit", async () => {
    const harness = createHardwareDashboardHarness();
    installHardwareDashboardFetchMock(harness);

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /^machine$/i }));

    const paperPanel = (await screen.findByRole("heading", { name: /^paper setup$/i })).closest(
      ".machine-paper-panel",
    );
    expect(paperPanel).not.toBeNull();
    const pageSizeGroup = within(paperPanel as HTMLElement)
      .getByText(/^page size$/i)
      .closest(".machine-paper-group");
    expect(pageSizeGroup).not.toBeNull();

    const pageWidthInput = await within(pageSizeGroup as HTMLElement).findByLabelText(/^width$/i);
    const saveButton = within(paperPanel as HTMLElement).getByRole("button", {
      name: /save paper setup/i,
    });

    fireEvent.change(pageWidthInput, { target: { value: "400" } });

    await waitFor(() => {
      expect(pageWidthInput).toHaveValue(400);
      expect(saveButton).toBeDisabled();
    });
    expect(harness.workspaceRequests).toHaveLength(0);
  });

  it("saves safe bounds and dispatches a plotter diagnostic action on the Machine tab", async () => {
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
    });
    installHardwareDashboardFetchMock(harness);

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /^machine$/i }));

    expect(await screen.findByRole("heading", { name: /^plotter$/i })).toBeInTheDocument();
    const paperPanel = screen.getByRole("heading", { name: /^paper setup$/i }).closest(
      ".machine-paper-panel",
    );
    expect(paperPanel).not.toBeNull();
    const safeBounds = within(paperPanel as HTMLElement)
      .getByText(/^safe bounds$/i)
      .closest(".machine-safe-bounds");
    expect(safeBounds).not.toBeNull();
    fireEvent.change(within(safeBounds as HTMLElement).getByLabelText(/^width$/i), {
      target: { value: "250" },
    });
    fireEvent.change(within(safeBounds as HTMLElement).getByLabelText(/^height$/i), {
      target: { value: "180" },
    });
    fireEvent.click(within(safeBounds as HTMLElement).getByRole("button", { name: /^save$/i }));

    expect(await screen.findByText(/operational safe bounds updated\./i)).toBeInTheDocument();
    expect(harness.safeBoundsRequests[0]).toEqual({
      width_mm: 250,
      height_mm: 180,
    });

    fireEvent.click(screen.getByRole("button", { name: /disengage motors/i }));

    expect(harness.plotterTestActions).toEqual(["align"]);
  });
});
