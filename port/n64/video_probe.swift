// Inspect a recorded gameplay video and export a frame for visual verification.
import Foundation
import AVFoundation
import AppKit

@main struct Probe {
    static func main() async throws {
        guard CommandLine.arguments.count == 4 else { print("video-probe video.mp4 seconds output.png"); return }
        let asset=AVURLAsset(url:URL(fileURLWithPath:CommandLine.arguments[1]))
        let duration=try await asset.load(.duration)
        for track in try await asset.load(.tracks) {
            let size=try await track.load(.naturalSize), frames=try await track.load(.nominalFrameRate)
            print("\(track.mediaType.rawValue): \(size) at \(frames) fps")
        }
        print("Duration: \(CMTimeGetSeconds(duration)) seconds")
        if let track = try await asset.loadTracks(withMediaType:.audio).first {
            let reader=try AVAssetReader(asset:asset)
            let output=AVAssetReaderTrackOutput(track:track,outputSettings:[AVFormatIDKey:kAudioFormatLinearPCM,
                AVLinearPCMIsFloatKey:true,AVLinearPCMBitDepthKey:32,AVLinearPCMIsNonInterleaved:false])
            reader.add(output);reader.startReading()
            var sum:Double=0,peak:Float=0,count=0
            while let sample=output.copyNextSampleBuffer() {
                guard let block=CMSampleBufferGetDataBuffer(sample) else { continue }
                var pointer:UnsafeMutablePointer<Int8>?;var length=0
                if CMBlockBufferGetDataPointer(block,atOffset:0,lengthAtOffsetOut:nil,totalLengthOut:&length,dataPointerOut:&pointer)==0,
                    let pointer=pointer {
                    pointer.withMemoryRebound(to:Float.self,capacity:length/4) { samples in
                        for i in 0..<(length/4) {let value=samples[i];sum+=Double(value*value);peak=max(peak,abs(value));count+=1}
                    }
                }
            }
            print("Audio PCM: \(count) samples; peak \(peak); RMS \(sqrt(sum/Double(max(count,1))))")
        }
        let generator=AVAssetImageGenerator(asset:asset)
        generator.appliesPreferredTrackTransform=true
        generator.requestedTimeToleranceBefore = .zero
        generator.requestedTimeToleranceAfter = .zero
        let result=try await generator.image(at:CMTime(seconds:Double(CommandLine.arguments[2]) ?? 1,preferredTimescale:600))
        let bitmap=NSBitmapImageRep(cgImage:result.image)
        try bitmap.representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:CommandLine.arguments[3]))
    }
}
