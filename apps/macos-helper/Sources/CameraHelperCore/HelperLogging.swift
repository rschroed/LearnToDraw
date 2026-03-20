import Foundation

public enum HelperLogger {
    private static let formatter = ISO8601DateFormatter()

    public static func log(instanceID: String, message: String) {
        let timestamp = formatter.string(from: Date())
        fputs("[LearnToDrawHelper instance=\(instanceID) at=\(timestamp)] \(message)\n", stderr)
    }
}
