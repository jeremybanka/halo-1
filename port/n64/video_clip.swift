// Copy a bounded section of an actual gameplay capture; no generated frames.
import Foundation
import AVFoundation
@main struct Clip {
    static func main() async throws {
        let a=CommandLine.arguments
        guard (a.count==5||a.count==6),let start=Double(a[2]),let duration=Double(a[3]),start>=0,duration>0 else {
            print("video-clip input.mp4 start-seconds duration-seconds output.mp4 [playback-rate]");exit(2)
        }
        let asset=AVURLAsset(url:URL(fileURLWithPath:a[1]))
        let rate=a.count==6 ? Double(a[5]) ?? 0 : 1
        guard rate>=0.1&&rate<=4 else {print("Playback rate must be 0.1..4");exit(2)}
        let range=CMTimeRange(start:CMTime(seconds:start,preferredTimescale:600),duration:CMTime(seconds:duration,preferredTimescale:600))
        let source:AVAsset
        if rate==1 {source=asset} else {
            // Change only playback timing. No synthesized/interpolated frames.
            let composition=AVMutableComposition()
            for track in try await asset.load(.tracks) {
                guard let destination=composition.addMutableTrack(withMediaType:track.mediaType,preferredTrackID:kCMPersistentTrackID_Invalid) else {continue}
                try destination.insertTimeRange(range,of:track,at:.zero)
                destination.preferredTransform=try await track.load(.preferredTransform)
            }
            composition.scaleTimeRange(CMTimeRange(start:.zero,duration:range.duration),toDuration:CMTimeMultiplyByFloat64(range.duration,multiplier:1/rate))
            source=composition
        }
        guard let session=AVAssetExportSession(asset:source,presetName:rate==1 ? AVAssetExportPresetPassthrough : AVAssetExportPresetHighestQuality) else {exit(3)}
        if rate==1 {session.timeRange=range}
        try await session.export(to:URL(fileURLWithPath:a[4]),as:.mp4)
        print("Saved \(a[4])")
    }
}
