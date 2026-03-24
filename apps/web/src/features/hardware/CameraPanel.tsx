import { useEffect, useMemo, useState } from "react";

import { HardwareCard } from "../../components/HardwareCard";
import type { DeviceStatus } from "../../types/hardware";
import { CameraDeviceSelector } from "./CameraDeviceSelector";
import { CameraFooterNote } from "./CameraFooterNote";
import {
  buildCameraPanelModel,
  parseCameraStatus,
} from "./cameraPanelModel";
import type { ActionFeedback } from "./hardwareDashboardTypes";

interface CameraPanelProps {
  cameraStatus: DeviceStatus;
  actionName: string | null;
  actionFeedback: ActionFeedback | null;
  capture: () => Promise<void>;
  setCameraDevice: (deviceId: string | null) => Promise<void>;
}

export function CameraPanel({
  cameraStatus,
  actionName,
  actionFeedback,
  capture,
  setCameraDevice,
}: CameraPanelProps) {
  const parsedStatus = useMemo(() => parseCameraStatus(cameraStatus), [cameraStatus]);
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const deviceIdsKey =
    parsedStatus.kind === "camerabridge"
      ? parsedStatus.details.devices.map((device) => device.id).join("|")
      : "";

  useEffect(() => {
    if (parsedStatus.kind !== "camerabridge") {
      return;
    }
    setSelectedDeviceId(
      parsedStatus.details.effective_selected_device_id ??
        parsedStatus.details.persisted_selected_device_id ??
        parsedStatus.details.devices[0]?.id ??
        "",
    );
  }, [
    deviceIdsKey,
    parsedStatus,
    parsedStatus.kind === "camerabridge"
      ? parsedStatus.details.effective_selected_device_id
      : null,
    parsedStatus.kind === "camerabridge"
      ? parsedStatus.details.persisted_selected_device_id
      : null,
  ]);

  const model = buildCameraPanelModel({
    parsedStatus,
    actionFeedback,
    actionName,
    selectedDeviceId,
  });

  return (
    <HardwareCard
      title="Camera"
      actionLabel="Capture image"
      status={cameraStatus}
      onAction={capture}
      actionPending={model.capturePending}
      actionDisabled={model.captureDisabled}
      notice={model.notice}
      footer={<CameraFooterNote note={model.footerNote} />}
    >
      {parsedStatus.kind === "camerabridge" && model.selectionRequired ? (
        <CameraDeviceSelector
          devices={model.availableDevices}
          selectedDeviceId={model.selectedDeviceId}
          savePending={model.saveDevicePending}
          saveDisabled={model.saveDeviceDisabled}
          onSelectedDeviceChange={setSelectedDeviceId}
          onSave={() => void setCameraDevice(model.selectedDeviceId)}
        />
      ) : null}
    </HardwareCard>
  );
}
