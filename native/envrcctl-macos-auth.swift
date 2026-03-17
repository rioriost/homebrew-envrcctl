import Foundation
import LocalAuthentication
import Security

enum HelperError: Error, LocalizedError {
    case invalidArguments(String)
    case authenticationUnavailable(String)
    case authenticationFailed(String)
    case keychainFailure(String)
    case decodeFailure

    var errorDescription: String? {
        switch self {
        case .invalidArguments(let message):
            return message
        case .authenticationUnavailable(let message):
            return message
        case .authenticationFailed(let message):
            return message
        case .keychainFailure(let message):
            return message
        case .decodeFailure:
            return "Keychain item contains non-UTF-8 data."
        }
    }
}

struct Arguments {
    let authorizeOnly: Bool
    let service: String?
    let account: String?
    let reason: String
}

private func printErrorAndExit(_ error: Error) -> Never {
    let message: String
    if let helperError = error as? LocalizedError, let description = helperError.errorDescription {
        message = description
    } else {
        message = "macOS authentication helper failed."
    }
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

private func parseArguments(_ argv: [String]) throws -> Arguments {
    var authorizeOnly = false
    var service: String?
    var account: String?
    var reason: String?

    var index = 1
    while index < argv.count {
        let arg = argv[index]
        switch arg {
        case "--authorize-only":
            authorizeOnly = true
            index += 1
        case "--service":
            guard index + 1 < argv.count else {
                throw HelperError.invalidArguments("Missing value for --service.")
            }
            service = argv[index + 1]
            index += 2
        case "--account":
            guard index + 1 < argv.count else {
                throw HelperError.invalidArguments("Missing value for --account.")
            }
            account = argv[index + 1]
            index += 2
        case "--reason":
            guard index + 1 < argv.count else {
                throw HelperError.invalidArguments("Missing value for --reason.")
            }
            reason = argv[index + 1]
            index += 2
        case "--help", "-h":
            let help = """
                Usage:
                  envrcctl-macos-auth --authorize-only --reason <text>
                  envrcctl-macos-auth --service <service> --account <account> --reason <text>

                Options:
                  --authorize-only   Require device owner authentication only.
                  --service          Keychain service name.
                  --account          Keychain account name.
                  --reason           Localized reason shown in the auth prompt.
                  --help             Show this help.
                """
            print(help)
            exit(0)
        default:
            throw HelperError.invalidArguments("Unknown argument: \(arg)")
        }
    }

    guard let reason, !reason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
        throw HelperError.invalidArguments("A non-empty --reason is required.")
    }

    if authorizeOnly {
        if service != nil || account != nil {
            throw HelperError.invalidArguments(
                "--authorize-only cannot be combined with --service or --account."
            )
        }
    } else {
        guard let service, !service.isEmpty else {
            throw HelperError.invalidArguments("--service is required.")
        }
        guard let account, !account.isEmpty else {
            throw HelperError.invalidArguments("--account is required.")
        }
        return Arguments(
            authorizeOnly: false,
            service: service,
            account: account,
            reason: reason
        )
    }

    return Arguments(
        authorizeOnly: true,
        service: nil,
        account: nil,
        reason: reason
    )
}

private func authenticate(reason: String) throws -> LAContext {
    let context = LAContext()
    context.localizedCancelTitle = "Cancel"

    var canEvaluateError: NSError?
    guard context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &canEvaluateError) else {
        let message =
            canEvaluateError?.localizedDescription
            ?? "Device owner authentication is unavailable."
        throw HelperError.authenticationUnavailable(message)
    }

    let semaphore = DispatchSemaphore(value: 0)
    var authError: Error?

    context.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: reason) { success, error in
        if !success {
            authError = error ?? HelperError.authenticationFailed("Authentication failed.")
        }
        semaphore.signal()
    }

    semaphore.wait()

    if let authError {
        if let laError = authError as? LAError {
            switch laError.code {
            case .userCancel, .userFallback, .systemCancel, .appCancel:
                throw HelperError.authenticationFailed("Authentication cancelled.")
            default:
                throw HelperError.authenticationFailed(laError.localizedDescription)
            }
        }
        throw HelperError.authenticationFailed(authError.localizedDescription)
    }

    return context
}

private func readSecret(service: String, account: String, context: LAContext) throws -> String {
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: service,
        kSecAttrAccount as String: account,
        kSecReturnData as String: true,
        kSecMatchLimit as String: kSecMatchLimitOne,
        kSecUseAuthenticationContext as String: context,
    ]

    var item: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &item)

    guard status == errSecSuccess else {
        let message = SecCopyErrorMessageString(status, nil) as String? ?? "Keychain read failed."
        throw HelperError.keychainFailure(message)
    }

    guard let data = item as? Data else {
        throw HelperError.keychainFailure("Keychain returned an unexpected item type.")
    }
    guard let value = String(data: data, encoding: .utf8) else {
        throw HelperError.decodeFailure
    }
    return value
}

do {
    let args = try parseArguments(CommandLine.arguments)
    let context = try authenticate(reason: args.reason)

    if args.authorizeOnly {
        exit(0)
    }

    guard let service = args.service, let account = args.account else {
        throw HelperError.invalidArguments("Both --service and --account are required.")
    }

    let secret = try readSecret(service: service, account: account, context: context)
    FileHandle.standardOutput.write(Data(secret.utf8))
    exit(0)
} catch {
    printErrorAndExit(error)
}
