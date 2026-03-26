import type { CameraBridgeDeviceOption } from "../../types/hardware";

interface CameraDeviceSelectorProps {
  devices: CameraBridgeDeviceOption[];
  selectedDeviceId: string;
  savedDeviceLabel: string | null;
  hasSelectionDraft: boolean;
  helperText: string | null;
  editLabel: string | null;
  savePending: boolean;
  saveDisabled: boolean;
  onSelectedDeviceChange: (deviceId: string) => void;
  onSave: () => void;
  onCancel: (() => void) | null;
  onEdit: (() => void) | null;
}

export function CameraDeviceSelector({
  devices,
  selectedDeviceId,
  savedDeviceLabel,
  hasSelectionDraft,
  helperText,
  editLabel,
  savePending,
  saveDisabled,
  onSelectedDeviceChange,
  onSave,
  onCancel,
  onEdit,
}: CameraDeviceSelectorProps) {
  const showCurrentValue = Boolean(editLabel && onEdit) || !savedDeviceLabel;
  const showActionRow = hasSelectionDraft;

  if (editLabel && onEdit && savedDeviceLabel) {
    return (
      <div className="camera-device-control camera-device-control-compact">
        <button
          type="button"
          className="button-primary button-compact"
          onClick={onEdit}
          aria-label="Edit camera selection"
        >
          Change
        </button>
      </div>
    );
  }

  return (
    <div className="camera-device-control">
      <div className="camera-device-header">
        <div>
          <p className="camera-selection-label">Selected camera</p>
          {showCurrentValue ? (
            <p className="camera-selection-current">
              {savedDeviceLabel ?? "No camera selected"}
            </p>
          ) : null}
        </div>
        {editLabel && onEdit ? (
          <button
            type="button"
            className="button-primary button-compact"
            onClick={onEdit}
            aria-label="Edit camera selection"
          >
            Change
          </button>
        ) : onCancel && !showActionRow ? (
          <button
            type="button"
            className="button-secondary button-compact"
            onClick={onCancel}
          >
            Cancel
          </button>
        ) : null}
      </div>
      {editLabel && onEdit ? null : (
        <div className="camera-device-editor">
          {helperText ? (
            <p className="camera-selection-helper">{helperText}</p>
          ) : null}
          <label>
            Choose camera
            <select
              value={selectedDeviceId}
              onChange={(event) => onSelectedDeviceChange(event.target.value)}
              style={{ marginTop: 8 }}
            >
              {devices.map((device) => (
                <option key={device.id} value={device.id}>
                  {formatDeviceLabel(device)}
                </option>
              ))}
            </select>
          </label>
          {showActionRow ? (
            <div className="actions camera-device-actions" style={{ marginTop: 12 }}>
              <button
                type="button"
                className="button-primary button-compact"
                disabled={saveDisabled}
                onClick={onSave}
              >
                {savePending ? "Saving..." : "Save camera"}
              </button>
              {onCancel ? (
                <button
                  type="button"
                  className="button-ghost button-compact"
                  onClick={onCancel}
                >
                  Cancel
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

function formatDeviceLabel(device: CameraBridgeDeviceOption) {
  const position =
    device.position === "external"
      ? "External"
      : device.position === "front"
        ? "Front"
        : "Back";
  return `${device.name} · ${position}`;
}
