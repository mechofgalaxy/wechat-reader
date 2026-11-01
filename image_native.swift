// Local ImageIO decode and optional Vision OCR. No network or WeChat APIs.
import Foundation
import ImageIO
import UniformTypeIdentifiers
import Vision

func finish(_ data: [String: Any], _ code: Int32 = 0) -> Never {
    let output = (try? JSONSerialization.data(withJSONObject: data, options: [.sortedKeys])) ?? Data("{}".utf8)
    FileHandle.standardOutput.write(output)
    FileHandle.standardOutput.write(Data([10]))
    exit(code)
}
let args = Array(CommandLine.arguments.dropFirst())
guard args.count == 2, ["inspect", "render", "ocr"].contains(args[0]) else {
    finish(["ok": false, "code": "invalid_argument"], 1)
}
let input = FileHandle.standardInput.readDataToEndOfFile()
guard input.count > 0, input.count <= 64 * 1024 * 1024,
      let source = CGImageSourceCreateWithData(input as CFData, [kCGImageSourceShouldCache: false] as CFDictionary),
      CGImageSourceGetStatus(source) == .statusComplete,
      let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
      let width = properties[kCGImagePropertyPixelWidth] as? Int,
      let height = properties[kCGImagePropertyPixelHeight] as? Int,
      width > 0, height > 0, width <= 50000, height <= 50000,
      width <= 40_000_000 / height else {
    finish(["ok": false, "code": "invalid_or_oversized_image"], 1)
}
guard let image = CGImageSourceCreateImageAtIndex(source, 0, [kCGImageSourceShouldCacheImmediately: true] as CFDictionary),
      CGImageSourceGetStatusAtIndex(source, 0) == .statusComplete else {
    finish(["ok": false, "code": "image_decode_failed"], 1)
}
// Force full pixel materialization, rather than accepting a valid header alone.
guard let pixels = image.dataProvider?.data, CFDataGetLength(pixels) > 0 else {
    finish(["ok": false, "code": "image_decode_failed"], 1)
}
var result: [String: Any] = ["ok": true, "width": image.width, "height": image.height,
    "frame_count": CGImageSourceGetCount(source), "decoded_frame": 0,
    "orientation": properties[kCGImagePropertyOrientation] as? Int ?? 1,
    "source_type": CGImageSourceGetType(source) as String? ?? "unknown", "pixel_decode_verified": true]
if args[0] != "inspect" && args[1] != "-" {
    let url = URL(fileURLWithPath: args[1])
    guard !FileManager.default.fileExists(atPath: url.path),
          let destination = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil) else {
        finish(["ok": false, "code": "output_unavailable"], 1)
    }
    CGImageDestinationAddImage(destination, image, [kCGImagePropertyOrientation: result["orientation"]!] as CFDictionary)
    guard CGImageDestinationFinalize(destination) else {
        finish(["ok": false, "code": "png_encode_failed"], 1)
    }
    result["output_format"] = "png"
}
if args[0] == "ocr" {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["zh-Hans", "zh-Hant", "en-US"]
    let orientation = CGImagePropertyOrientation(rawValue: UInt32(result["orientation"] as? Int ?? 1)) ?? .up
    do {
        try VNImageRequestHandler(cgImage: image, orientation: orientation, options: [:]).perform([request])
        let observations = (request.results ?? []).prefix(2000)
        result["ocr"] = ["status": "ok", "engine": "Apple Vision (local)",
            "lines": observations.compactMap { observation -> [String: Any]? in
                guard let text = observation.topCandidates(1).first else { return nil }
                return ["text": String(text.string.prefix(4000)), "confidence": text.confidence]
            }]
    } catch {
        result["ocr"] = ["status": "failed", "code": "local_ocr_failed", "error_domain": (error as NSError).domain, "error_code": (error as NSError).code]
    }
}
finish(result)
