import { useEffect, useState } from "react";

import { HardwareCard } from "../../components/HardwareCard";
import {
  getCameraBridgeStatusDetails,
  type CameraBridgeStatusDetails,
  type DeviceStatus,
} from "../../types/hardware";
import type { ActionFeedback } from "./hardwareDashboardTypes";


interface CameraPanelProps {
  cameraStatus: DeviceStatus;
  actionName: string | null;
  actionFeedback: ActionFeedback | null;
  capture: () => Promise<void>;
  setCameraDevice: (deviceId: string | null) => Promise<void>;
}

function buildCameraNotice(
  cameraStatus: DeviceStatus,
  actionFeedback: ActionFeedback | null,
  details: CameraBridgeStatusDetails | null,
) {
  if (
    actionFeedback?.action === "camera-capture" ||
    actionFeedback?.action === "camera-device"
  ) {
    return {
      tone: actionFeedback.tone,
      message: actionFeedback.message,
    };
  }

  if (details !== null) {
    switch (details.readiness_state) {
      case "needs_service":
        return {
          tone: "info" as const,
          message:
            "Open CameraBridgeApp, click Start CameraBridge Service, then retry once the local service is running.",
        };
      case "needs_permission":
        return {
          tone: "info" as const,
          message:
            details.permission_message ??
            "Open CameraBridgeApp and request camera access before capturing.",
        };
      case "needs_device_selection":
        return {
          tone: "info" as const,
          message: "Choose a CameraBridge device to enable capture.",
        };
      case "busy_external":
        return {
          tone: "error" as const,
          message:
            "Another local client currently owns the CameraBridge session. Stop it there and retry.",
        };
      case "error":
        if (cameraStatus.error) {
          return { tone: "error" as const, message: cameraStatus.error };
        }
        return null;
      default:
        break;
    }
  }

  if (cameraStatus.error) {
    return { tone: "error" as const, message: cameraStatus.error };
  }

  return null;
}


export function CameraPanel({
  cameraStatus,
  actionName,
  actionFeedback,
  capture,
  setCameraDevice,
}: CameraPanelProps) {
  const cameraBridgeDetails = getCameraBridgeStatusDetails(cameraStatus);
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const deviceIdsKey =
    cameraBridgeDetails?.devices.map((device) => device.id).join("|") ?? "";

  useEffect(() => {
    if (cameraBridgeDetails === null) {
      return;
    }
    setSelectedDeviceId(
      cameraBridgeDetails.effective_selected_device_id ??
        cameraBridgeDetails.persisted_selected_device_id ??
        cameraBridgeDetails.devices[0]?.id ??
        "",
    );
  }, [
    deviceIdsKey,
    cameraBridgeDetails?.effective_selected_device_id,
    cameraBridgeDetails?.persisted_selected_device_id,
  ]);

  const captureDisabled =
    actionName === "camera-capture" ||
    cameraStatus.busy ||
    (cameraBridgeDetails !== null
      ? cameraBridgeDetails.readiness_state !== "ready"
      : !cameraStatus.available || cameraStatus.error !== null);
  const selectedDeviceLabel =
    cameraBridgeDetails?.devices.find(
      (device) => device.id === cameraBridgeDetails.effective_selected_device_id,
    )?.name ?? null;

  return (
    <HardwareCard
      title="Camera"
      actionLabel="Capture image"
      status={cameraStatus}
      onAction={capture}
      actionPending={actionName === "camera-capture"}
      actionDisabled={captureDisabled}
      notice={buildCameraNotice(cameraStatus, actionFeedback, cameraBridgeDetails)}
      footer={
        <p className="footer-note">
          {selectedDeviceLabel ? `Selected device: ${selectedDeviceLabel}. ` : ""}
          Captures are saved locally and served back through the backend.
        </p>
      }
    >
      {cameraBridgeDetails?.selection_required ? (
        <div className="diagnostic-panel" style={{ marginTop: 0, marginBottom: 18 }}>
          <div className="diagnostic-section">
            <h3>Camera device</h3>
            <label>
              Choose a device
              <select
                value={selectedDeviceId}
                onChange={(event) => setSelectedDeviceId(event.target.value)}
                style={{ marginTop: 8 }}
              >
                {cameraBridgeDetails.devices.map((device) => (
                  <option key={device.id} value={device.id}>
                    {device.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="actions" style={{ marginTop: 12 }}>
              <button
                type="button"
                className="button-secondary"
                disabled={actionName === "camera-device" || selectedDeviceId.length === 0}
                onClick={() => void setCameraDevice(selectedDeviceId)}
              >
                {actionName === "camera-device" ? "Saving..." : "Save camera"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </HardwareCard>
  );
}
