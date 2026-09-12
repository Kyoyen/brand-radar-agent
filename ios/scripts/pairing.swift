// Run from the repository root: swift ios/scripts/pairing.swift
// The credential stays in ignored local files. Do not publish the resulting QR.
import AppKit
import CoreImage
import Foundation

let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let file = root.appendingPathComponent("outputs/studio/phone-pairing.json")
let data = try Data(contentsOf: file)
let pairing = try JSONSerialization.jsonObject(with: data) as! [String: Any]
guard let urls = pairing["urls"] as? [String], let base = urls.first, let token = pairing["token"] as? String else {
    fatalError("先启动手机连接模式，再生成配对码。")
}
var components = URLComponents()
components.scheme = "brandradar"; components.host = "pair"
components.queryItems = [URLQueryItem(name: "url", value: base), URLQueryItem(name: "token", value: token)]
let filter = CIFilter(name: "CIQRCodeGenerator")!
filter.setValue(Data(components.url!.absoluteString.utf8), forKey: "inputMessage")
filter.setValue("M", forKey: "inputCorrectionLevel")
let qr = filter.outputImage!.transformed(by: CGAffineTransform(scaleX: 9, y: 9))
let cg = CIContext().createCGImage(qr, from: qr.extent)!
let bitmap = NSBitmapImageRep(cgImage: cg)
let png = bitmap.representation(using: .png, properties: [:])!
let output = root.appendingPathComponent("outputs/studio/phone-pairing.png")
try png.write(to: output, options: .atomic)
try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: output.path)
let html = """
<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Brand Radar · 连接 iPhone</title><style>body{margin:0;background:#f4f4ec;color:#233524;font-family:system-ui;text-align:center;padding:60px 20px}main{max-width:520px;margin:auto}h1{font-size:32px}p{line-height:1.8}img{width:290px;max-width:80vw;padding:24px;background:white;border-radius:24px}small{color:#667062}</style>
<main><small>BRAND RADAR</small><h1>把这张桌面，带到手机上。</h1><p>安装 App 后，用 iPhone 相机扫码。<br>手机与 Mac 连同一网络，Mac 保持运行。</p><img alt="iPhone 配对码" src="data:image/png;base64,\(png.base64EncodedString())"><p>Mac 地址：\(base)</p><small>配对码只用于你的本地连接，请保留在本机。</small></main></html>
"""
let page = root.appendingPathComponent("outputs/studio/phone-pairing.html")
try Data(html.utf8).write(to: page, options: .atomic)
try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: page.path)
print("配对页已生成：outputs/studio/phone-pairing.html")
