import type { CameraBridgeDeviceOption } from "../../types/hardware";

interface CameraDeviceSelectorProps {
  devices: CameraBridgeDeviceOption[];
  selectedDeviceId: string;
  savePending: boolean;
  saveDisabled: boolean;
  onSelectedDeviceChange: (deviceId: string) => void;
  onSave: () => void;
}

export function CameraDeviceSelector({
  devices,
  selectedDeviceId,
  savePending,
  saveDisabled,
  onSelectedDeviceChange,
  onSave,
}: CameraDeviceSelectorProps) {
  return (
    <div className="diagnostic-panel" style={{ marginTop: 0, marginBottom: 18 }}>
      <div className="diagnostic-section">
        <h3>Camera device</h3>
        <label>
          Choose a device
          <select
            value={selectedDeviceId}
            onChange={(event) => onSelectedDeviceChange(event.target.value)}
            style={{ marginTop: 8 }}
          >
            {devices.map((device) => (
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
            disabled={saveDisabled}
            onClick={onSave}
          >
            {savePending ? "Saving..." : "Save camera"}
          </button>
        </div>
      </div>
    </div>
  );
}
