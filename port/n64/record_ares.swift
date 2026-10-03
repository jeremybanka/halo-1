// Record only the requested ares game window, with its application audio.
// macOS 15+: swiftc -parse-as-library record_ares.swift -o build/n64/record-ares
import Foundation
import ScreenCaptureKit
import AVFoundation
import AppKit

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

@main struct Recorder {
    @MainActor static func main() async throws {
        _ = NSApplication.shared
        let args = CommandLine.arguments
        guard args.count == 4, let seconds = Double(args[3]), seconds > 0, seconds <= 180 else {
            print("Usage: record-ares exact-window-title output.mp4 seconds (1..180)")
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
        let stream = SCStream(filter: filter, configuration: config, delegate: nil)
        let recordingConfig = SCRecordingOutputConfiguration()
        recordingConfig.outputURL = URL(fileURLWithPath: args[2])
        recordingConfig.videoCodecType = .h264
        recordingConfig.outputFileType = .mp4
        let delegate = RecordingDelegate()
        let recording = SCRecordingOutput(configuration: recordingConfig, delegate: delegate)
        try stream.addRecordingOutput(recording)
        try await stream.startCapture()
        try await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
        try await stream.stopCapture()
        for _ in 0..<100 where !delegate.finished {
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        if let error = delegate.failure { throw error }
        guard delegate.finished else { throw NSError(domain: "record-ares", code: 4) }
        let asset = AVURLAsset(url: recordingConfig.outputURL)
        let duration = try await asset.load(.duration)
        let tracks = try await asset.load(.tracks)
        print("Saved \(args[2]); \(CMTimeGetSeconds(duration)) seconds; \(tracks.count) tracks")
    }
}
