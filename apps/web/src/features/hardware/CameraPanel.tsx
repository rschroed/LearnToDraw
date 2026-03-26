import { useEffect, useMemo, useState, type ReactNode } from "react";

import { StatusPill } from "../../components/StatusPill";
import { openCameraBridgeApp } from "../../lib/api";
import type { DeviceStatus } from "../../types/hardware";
import { CameraDeviceSelector } from "./CameraDeviceSelector";
import { buildCameraPanelModel, parseCameraStatus } from "./cameraPanelModel";
import type { ActionFeedback } from "./hardwareDashboardTypes";

function CameraSummary({
  title,
  detail,
  action,
  children,
}: {
  title: string;
  detail: string | null;
  action?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="camera-summary camera-setup-summary">
      <div className="camera-summary-copy">
        <p className="camera-selection-label">Selected camera</p>
        <h3>{title}</h3>
        {detail ? <p className="camera-summary-detail">{detail}</p> : null}
      </div>
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
    deviceIdsKey,
    editingDevice,
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
  const statusLabel = model.headerStatusLabel ?? "Ready";
  const driverLabel =
    cameraStatus.driver === "camerabridge" ? "CameraBridge" : cameraStatus.driver;
  const summaryTitle = model.savedDeviceLabel ?? model.summaryTitle;
  const summaryDetail = [`Driver ${driverLabel}`, statusLabel].join(" · ");

  return (
    <section className="panel machine-camera-panel">
      <header className="machine-quiet-header">
        <div>
          <h2>Camera</h2>
        </div>
        <StatusPill label="State" value={statusLabel} tone={model.headerStatusTone} />
      </header>

      {model.notice ? (
        <div className={`inline-notice inline-notice-${model.notice.tone}`}>{model.notice.message}</div>
      ) : null}

      <CameraSummary
        title={summaryTitle}
        detail={summaryDetail}
        action={
          <>
            {model.secondaryActionLabel && model.secondaryActionIntent === "open_camera_bridge_app" ? (
              <button
                type="button"
                className="button-primary"
                onClick={openCameraBridgeApp}
              >
                {model.secondaryActionLabel}
              </button>
            ) : null}
            <button
              type="button"
              className="button-secondary"
              onClick={() => void capture()}
              disabled={model.captureDisabled}
            >
              {model.capturePending ? model.capturePendingLabel : model.captureActionLabel}
            </button>
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
        {parsedStatus.kind === "camerabridge" && model.canEditDevice ? null : model.summaryDetail ? (
          <p className="camera-summary-detail">{model.summaryDetail}</p>
        ) : null}
      </CameraSummary>
    </section>
  );
}
