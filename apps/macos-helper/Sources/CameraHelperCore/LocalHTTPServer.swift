import Foundation
import Network

public final class LocalHTTPServer {
    private let controller: HelperController
    private let host: NWEndpoint.Host
    private let port: NWEndpoint.Port
    private let queue = DispatchQueue(label: "learn-to-draw.camera-helper.http")
    private var listener: NWListener?
    private let encoder: JSONEncoder

    public init(
        controller: HelperController,
        host: String = "127.0.0.1",
        port: UInt16 = 8001
    ) {
        self.controller = controller
        self.host = NWEndpoint.Host(host)
        self.port = NWEndpoint.Port(rawValue: port) ?? 8001
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys]
        self.encoder = encoder
    }

    public func start() throws {
        let parameters = NWParameters.tcp
        parameters.allowLocalEndpointReuse = true
        parameters.requiredLocalEndpoint = .hostPort(host: host, port: port)
        let listener = try NWListener(using: parameters)
        listener.newConnectionHandler = { [weak self] connection in
            self?.handle(connection: connection)
        }
        listener.stateUpdateHandler = { state in
            if case .failed(let error) = state {
                fputs("Helper HTTP listener failed: \(error)\n", stderr)
            }
        }
        listener.start(queue: queue)
        self.listener = listener
    }

    public func stop() {
        listener?.cancel()
        listener = nil
    }

    private func handle(connection: NWConnection) {
        connection.start(queue: queue)
        connection.receive(minimumIncompleteLength: 1, maximumLength: 65_536) { [weak self] data, _, _, _ in
            guard let self else {
                connection.cancel()
                return
            }

            let request = Self.parseRequest(data: data)
            Task {
                let response = await self.route(request: request)
                connection.send(content: response, completion: .contentProcessed { _ in
                    connection.cancel()
                })
            }
        }
    }

    private func route(request: ParsedRequest) async -> Data {
        switch (request.method, request.path) {
        case ("GET", "/status"), ("GET", "/local-helper/status"):
            let status = await controller.status()
            return makeJSONResponse(statusCode: 200, payload: status)
        case ("POST", "/start"), ("POST", "/local-helper/start"):
            let status = await controller.start()
            return makeJSONResponse(statusCode: 200, payload: status)
        case ("POST", "/stop"), ("POST", "/local-helper/stop"):
            let status = await controller.stop()
            return makeJSONResponse(statusCode: 200, payload: status)
        case ("POST", "/restart"), ("POST", "/local-helper/restart"):
            let status = await controller.restart()
            return makeJSONResponse(statusCode: 200, payload: status)
        default:
            return makeTextResponse(statusCode: 404, body: "Not found")
        }
    }

    private func makeJSONResponse<T: Encodable>(statusCode: Int, payload: T) -> Data {
        do {
            let body = try encoder.encode(payload)
            return response(
                statusCode: statusCode,
                contentType: "application/json",
                body: body
            )
        } catch {
            return makeTextResponse(statusCode: 500, body: "Encoding error")
        }
    }

    private func makeTextResponse(statusCode: Int, body: String) -> Data {
        response(
            statusCode: statusCode,
            contentType: "text/plain; charset=utf-8",
            body: Data(body.utf8)
        )
    }

    private func response(statusCode: Int, contentType: String, body: Data) -> Data {
        let header = [
            "HTTP/1.1 \(statusCode) \(Self.reasonPhrase(for: statusCode))",
            "Content-Type: \(contentType)",
            "Content-Length: \(body.count)",
            "Connection: close",
            "",
            "",
        ].joined(separator: "\r\n")
        var response = Data(header.utf8)
        response.append(body)
        return response
    }

    private static func parseRequest(data: Data?) -> ParsedRequest {
        guard
            let data,
            let text = String(data: data, encoding: .utf8),
            let firstLine = text.components(separatedBy: "\r\n").first
        else {
            return ParsedRequest(method: "", path: "")
        }

        let parts = firstLine.split(separator: " ", omittingEmptySubsequences: true)
        guard parts.count >= 2 else {
            return ParsedRequest(method: "", path: "")
        }

        return ParsedRequest(method: String(parts[0]), path: String(parts[1]))
    }

    private static func reasonPhrase(for statusCode: Int) -> String {
        switch statusCode {
        case 200:
            return "OK"
        case 404:
            return "Not Found"
        default:
            return "Internal Server Error"
        }
    }
}

private struct ParsedRequest {
    let method: String
    let path: String
}
