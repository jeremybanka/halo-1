// Record only the requested ares game window, with its application audio.
// macOS 15+: swiftc -parse-as-library record_ares.swift -o build/n64/record-ares
import Foundation
import ScreenCaptureKit
import AVFoundation
import AppKit
import ImageIO
import UniformTypeIdentifiers

final class RecordingDelegate: NSObject, SCRecordingOutputDelegate {
    var finished = false
    var failure: Error?
    func recordingOutputDidStartRecording(_ output: SCRecordingOutput) {
        print("Recording ares window")
        fflush(stdout)
    }
    func recordingOutputDidFinishRecording(_ output: SCRecordingOutput) { finished = true }
    func recordingOutput(_ output: SCRecordingOutput, didFailWithError error: Error) {
        failure = error; finished = true
    }
}


// Keep one complete screen buffer on a serial queue, then write its pixels
// directly to PNG. Idle frames may carry no image, so a frozen scene can use
// the latest complete buffer without manufacturing a new frame.
final class RawFrameOutput: NSObject, SCStreamOutput, @unchecked Sendable {
    let queue = DispatchQueue(label: "halo.ares.lossless-frame")
    private let outputURL: URL
    private var latest: CVPixelBuffer?
    private var requested = false
    private var saved = false
    private var failure: Error?
    init(path: String) { outputURL = URL(fileURLWithPath: path) }

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer,
                of type: SCStreamOutputType) {
        guard type == .screen, sampleBuffer.isValid,
              let attachments = CMSampleBufferGetSampleAttachmentsArray(sampleBuffer, createIfNecessary: false)
                as? [[SCStreamFrameInfo: Any]],
              let status = attachments.first?[.status] as? Int,
              status == SCFrameStatus.complete.rawValue,
              let buffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        guard !saved, failure == nil else { return }
        latest = buffer
        if requested { writeLatest() }
    }

    func requestPNG() {
        queue.async { self.requested = true; self.writeLatest() }
    }

    private func writeLatest() {
        guard requested, !saved, failure == nil, let buffer = latest else { return }
        do {
            guard CVPixelBufferGetPixelFormatType(buffer) == kCVPixelFormatType_32BGRA else {
                throw NSError(domain: "record-ares-raw", code: 5,
                    userInfo: [NSLocalizedDescriptionKey: "Expected BGRA screen pixels"])
            }
            CVPixelBufferLockBaseAddress(buffer, .readOnly)
            defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
            let width = CVPixelBufferGetWidth(buffer), height = CVPixelBufferGetHeight(buffer)
            let stride = CVPixelBufferGetBytesPerRow(buffer)
            guard let base = CVPixelBufferGetBaseAddress(buffer) else {
                throw NSError(domain: "record-ares-raw", code: 6)
            }
            // Copy the full buffer, including its native row stride; CGImage
            // handles padding. No video decode, crop, filtering or rescaling.
            let pixels = Data(bytes: base, count: stride * height)
            let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)!
            let bitmapInfo = CGBitmapInfo.byteOrder32Little.union(
                CGBitmapInfo(rawValue: CGImageAlphaInfo.premultipliedFirst.rawValue))
            guard let provider = CGDataProvider(data: pixels as CFData),
                  let image = CGImage(width: width, height: height, bitsPerComponent: 8,
                    bitsPerPixel: 32, bytesPerRow: stride, space: colorSpace,
                    bitmapInfo: bitmapInfo, provider: provider, decode: nil,
                    shouldInterpolate: false, intent: .defaultIntent),
                  let destination = CGImageDestinationCreateWithURL(outputURL as CFURL,
                    UTType.png.identifier as CFString, 1, nil) else {
                throw NSError(domain: "record-ares-raw", code: 7)
            }
            CGImageDestinationAddImage(destination, image, nil)
            guard CGImageDestinationFinalize(destination) else {
                throw NSError(domain: "record-ares-raw", code: 8)
            }
            saved = true
            latest = nil
            print("Saved raw PNG \(outputURL.path); \(width)x\(height) BGRA screen pixels")
            fflush(stdout)
        } catch { failure = error; latest = nil }
    }

    func verifySaved() throws {
        try queue.sync {
            if let error = failure { throw error }
            guard saved else {
                throw NSError(domain: "record-ares-raw", code: 9,
                    userInfo: [NSLocalizedDescriptionKey: "No complete screen frame available for PNG"])
            }
        }
    }
}

@main struct Recorder {
    @MainActor static func main() async throws {
        _ = NSApplication.shared
        let args = CommandLine.arguments
        guard (args.count == 4 || args.count == 5), let seconds = Double(args[3]), seconds > 0, seconds <= 180 else {
            print("Usage: record-ares exact-window-title output.mp4 seconds (1..180) [raw-frame.png]")
            exit(2)
        }
        let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
        let matches = content.windows.filter {
            $0.owningApplication?.bundleIdentifier == "dev.ares.ares" && $0.title == args[1]
        }
        guard matches.count == 1, let window = matches.first else {
            print("Expected one ares window named \(args[1]); found \(matches.count)")
            exit(3)
        }
        let filter = SCContentFilter(desktopIndependentWindow: window)
        let config = SCStreamConfiguration()
        config.width = 960
        config.height = 768
        config.minimumFrameInterval = CMTime(value: 1, timescale: 30)
        config.queueDepth = 5
        config.showsCursor = false
        config.capturesAudio = true
        config.excludesCurrentProcessAudio = true
        config.sampleRate = 48000
        config.channelCount = 2
        config.captureMicrophone = false
        let rawFrame = args.count == 5 ? RawFrameOutput(path: args[4]) : nil
        if rawFrame != nil { config.pixelFormat = kCVPixelFormatType_32BGRA }
        let stream = SCStream(filter: filter, configuration: config, delegate: nil)
        if let rawFrame = rawFrame {
            try stream.addStreamOutput(rawFrame, type: .screen, sampleHandlerQueue: rawFrame.queue)
        }
        let recordingConfig = SCRecordingOutputConfiguration()
        recordingConfig.outputURL = URL(fileURLWithPath: args[2])
        recordingConfig.videoCodecType = .h264
        recordingConfig.outputFileType = .mp4
        let delegate = RecordingDelegate()
        let recording = SCRecordingOutput(configuration: recordingConfig, delegate: delegate)
        try stream.addRecordingOutput(recording)
        try await stream.startCapture()
        if let rawFrame = rawFrame {
            let captureAfter = min(1.0, seconds * 0.5)
            try await Task.sleep(nanoseconds: UInt64(captureAfter * 1_000_000_000))
            rawFrame.requestPNG()
            try await Task.sleep(nanoseconds: UInt64((seconds - captureAfter) * 1_000_000_000))
        } else {
            try await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
        }
        try await stream.stopCapture()
        for _ in 0..<100 where !delegate.finished {
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        if let error = delegate.failure { throw error }
        try rawFrame?.verifySaved()
        guard delegate.finished else { throw NSError(domain: "record-ares", code: 4) }
        let asset = AVURLAsset(url: recordingConfig.outputURL)
        let duration = try await asset.load(.duration)
        let tracks = try await asset.load(.tracks)
        print("Saved \(args[2]); \(CMTimeGetSeconds(duration)) seconds; \(tracks.count) tracks")
    }
}
