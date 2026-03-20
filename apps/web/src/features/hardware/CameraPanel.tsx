import { HardwareCard } from "../../components/HardwareCard";
import type { DeviceStatus } from "../../types/hardware";
import type { ActionFeedback } from "./hardwareDashboardTypes";


interface CameraPanelProps {
  cameraStatus: DeviceStatus;
  actionName: string | null;
  actionFeedback: ActionFeedback | null;
  capture: () => Promise<void>;
}

function getStringDetail(details: Record<string, unknown>, key: string) {
  return typeof details[key] === "string" ? details[key] : null;
}

function getNumberDetail(details: Record<string, unknown>, key: string) {
  return typeof details[key] === "number" ? details[key] : null;
}

function buildCameraNotice(
  cameraStatus: DeviceStatus,
  actionFeedback: ActionFeedback | null,
) {
  if (cameraStatus.error) {
    const details = cameraStatus.details;
    const initializationState = getStringDetail(details, "initialization_state");
    const lastOpenResult = getStringDetail(details, "last_open_result");
    const lastReadResult = getStringDetail(details, "last_read_result");
    const lastOpenMessage = getStringDetail(details, "last_open_message");
    const cameraIndex = getNumberDetail(details, "camera_index");
    const isRetryableOpenCvFailure =
      cameraStatus.driver === "opencv-camera" && initializationState === "unavailable";

    if (!isRetryableOpenCvFailure) {
      return { tone: "error" as const, message: cameraStatus.error };
    }

    const failureReason =
      lastOpenResult === "failed"
        ? "OpenCV could not open the selected camera."
        : lastReadResult === "failed"
          ? "OpenCV opened the camera but failed to read a frame."
          : cameraStatus.error;
    const indexText = cameraIndex === null ? "unknown" : String(cameraIndex);
    const operatorHint =
      "Check macOS camera permission, confirm the device is not busy in another app, or relaunch with LEARN_TO_DRAW_OPENCV_CAMERA_INDEX set to the correct device.";

    return {
      tone: "error" as const,
      message: `${failureReason} Camera index ${indexText}. ${lastOpenMessage ?? cameraStatus.error} ${operatorHint}`,
    };
  }

  if (actionFeedback?.action === "camera-capture") {
    return {
      tone: actionFeedback.tone,
      message: actionFeedback.message,
    };
  }

  return null;
}


export function CameraPanel({
  cameraStatus,
  actionName,
  actionFeedback,
  capture,
}: CameraPanelProps) {
  const cameraInitializationState =
    typeof cameraStatus.details.initialization_state === "string"
      ? cameraStatus.details.initialization_state
      : null;
  const captureRetryable =
    cameraStatus.driver === "opencv-camera" &&
    (cameraInitializationState === "uninitialized" ||
      cameraInitializationState === "unavailable");
  const captureDisabled =
    actionName === "camera-capture" ||
    cameraStatus.busy ||
    (!cameraStatus.available && !captureRetryable) ||
    (cameraStatus.error !== null && !captureRetryable);

  return (
    <HardwareCard
      title="Camera"
      actionLabel="Capture image"
      status={cameraStatus}
      onAction={capture}
      actionPending={actionName === "camera-capture"}
      actionDisabled={captureDisabled}
      notice={buildCameraNotice(cameraStatus, actionFeedback)}
      footer={
        <p className="footer-note">
          Captures are saved locally and served back through the backend.
        </p>
      }
    />
  );
}
