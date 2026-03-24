import { useEffect, useMemo, useState, type ReactNode } from "react";

import { HardwareCard } from "../../components/HardwareCard";
import { openCameraBridgeApp } from "../../lib/api";
import { StatusPill } from "../../components/StatusPill";
import type { DeviceStatus } from "../../types/hardware";
import { CameraDeviceSelector } from "./CameraDeviceSelector";
import {
  buildCameraPanelModel,
  parseCameraStatus,
} from "./cameraPanelModel";
import type { ActionFeedback } from "./hardwareDashboardTypes";

function CameraSummary({
  title,
  detail,
  badges,
  action,
  children,
}: {
  title: string;
  detail: string | null;
  badges: string[];
  action?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="camera-summary">
      <div className="camera-summary-copy">
        <h3>{title}</h3>
        {detail ? <p className="camera-summary-detail">{detail}</p> : null}
      </div>
      {badges.length > 0 ? (
        <div className="camera-summary-badges">
          {badges.map((badge) => (
            <span key={badge} className="camera-summary-badge">
              {badge}
            </span>
          ))}
        </div>
      ) : null}
      {action ? <div className="camera-summary-actions">{action}</div> : null}
      {children}
    </div>
  );
}

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
  const [editingDevice, setEditingDevice] = useState(false);
  const deviceIdsKey =
    parsedStatus.kind === "camerabridge"
      ? parsedStatus.details.devices.map((device) => device.id).join("|")
      : "";
  const backendSelectedDeviceId =
    parsedStatus.kind === "camerabridge"
      ? parsedStatus.details.effective_selected_device_id ??
        parsedStatus.details.persisted_selected_device_id ??
        parsedStatus.details.devices[0]?.id ??
        ""
      : "";

  useEffect(() => {
    if (parsedStatus.kind !== "camerabridge") {
      return;
    }

    if (!editingDevice) {
      setSelectedDeviceId(backendSelectedDeviceId);
    }

    if (
      parsedStatus.details.selection_required ||
      parsedStatus.details.effective_selected_device_id === null
    ) {
      setEditingDevice(true);
    }
  }, [
    backendSelectedDeviceId,
    editingDevice,
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
  const showDeviceEditor =
    parsedStatus.kind === "camerabridge" &&
    model.canEditDevice &&
    (model.selectionRequired || editingDevice || model.savedDeviceLabel === null);

  return (
    <HardwareCard
      title="Camera"
      headerMeta={null}
      headerStatus={model.headerStatusLabel ? (
        <StatusPill
          label="State"
          value={model.headerStatusLabel}
          tone={model.headerStatusTone}
        />
      ) : null}
      hideStatusRow
      hideDetails
      summary={
        <CameraSummary
          title={model.summaryTitle}
          detail={model.summaryDetail}
          badges={model.summaryBadges}
          action={
            <>
              <button
                type="button"
                className="button-primary"
                onClick={() => void capture()}
                disabled={model.captureDisabled}
              >
                {model.capturePending ? model.capturePendingLabel : model.captureActionLabel}
              </button>
              {model.secondaryActionLabel && model.secondaryActionIntent === "open_camera_bridge_app" ? (
                <button
                  type="button"
                  className="button-secondary"
                  onClick={openCameraBridgeApp}
                >
                  {model.secondaryActionLabel}
                </button>
              ) : null}
            </>
          }
        >
          {parsedStatus.kind === "camerabridge" && model.canEditDevice ? (
            <CameraDeviceSelector
              devices={model.availableDevices}
              selectedDeviceId={model.selectedDeviceId}
              savedDeviceLabel={model.savedDeviceLabel}
              hasSelectionDraft={model.hasSelectionDraft}
              helperText={showDeviceEditor ? model.deviceSelectionHelper : null}
              editLabel={showDeviceEditor ? null : model.deviceEditLabel}
              savePending={model.saveDevicePending}
              saveDisabled={model.saveDeviceDisabled}
              onSelectedDeviceChange={setSelectedDeviceId}
              onSave={() =>
                void setCameraDevice(model.selectedDeviceId).then(() => {
                  setEditingDevice(false);
                })
              }
              onCancel={
                showDeviceEditor && !model.selectionRequired
                  ? () => {
                      setSelectedDeviceId(backendSelectedDeviceId);
                      setEditingDevice(false);
                    }
                  : null
              }
              onEdit={showDeviceEditor ? null : () => setEditingDevice(true)}
            />
          ) : null}
        </CameraSummary>
      }
      status={cameraStatus}
      notice={model.notice}
    />
  );
}
