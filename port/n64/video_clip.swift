// Copy a bounded section of an actual gameplay capture; no generated frames.
import Foundation
import AVFoundation
@main struct Clip {
    static func main() async throws {
        let a=CommandLine.arguments
        guard a.count==5,let start=Double(a[2]),let duration=Double(a[3]),start>=0,duration>0 else {
            print("video-clip input.mp4 start-seconds duration-seconds output.mp4");exit(2)
        }
        let asset=AVURLAsset(url:URL(fileURLWithPath:a[1]))
        guard let session=AVAssetExportSession(asset:asset,presetName:AVAssetExportPresetPassthrough) else {exit(3)}
        session.timeRange=CMTimeRange(start:CMTime(seconds:start,preferredTimescale:600),duration:CMTime(seconds:duration,preferredTimescale:600))
        try await session.export(to:URL(fileURLWithPath:a[4]),as:.mp4)
        print("Saved \(a[4])")
    }
}
