import SwiftUI
import UIKit

struct HoldToTalkControl: UIViewRepresentable {
    var title: String
    var voiceEnabled: Bool
    var active: Bool
    var liveDrawing: Bool
    var onTap: () -> Void
    var onBegin: () -> Void
    var onCancelChange: (Bool) -> Void
    var onEnd: (Bool) -> Void

    func makeUIView(context: Context) -> HoldToTalkView { HoldToTalkView() }
    func updateUIView(_ view: HoldToTalkView, context: Context) {
        view.configure(title: title, voiceEnabled: voiceEnabled, active: active, liveDrawing: liveDrawing,
                       onTap: onTap, onBegin: onBegin, onCancelChange: onCancelChange, onEnd: onEnd)
    }
    static func dismantleUIView(_ view: HoldToTalkView, coordinator: ()) { view.cancelIfNeeded() }
}

final class HoldToTalkView: UIView {
    private let control = HoldToTalkButton()
    override init(frame: CGRect) {
        super.init(frame: frame)
        accessibilityIdentifier = "holdToTalk"
        isAccessibilityElement = false
        control.translatesAutoresizingMaskIntoConstraints = false
        addSubview(control)
        NSLayoutConstraint.activate([
            control.leadingAnchor.constraint(equalTo: leadingAnchor), control.trailingAnchor.constraint(equalTo: trailingAnchor),
            control.topAnchor.constraint(equalTo: topAnchor), control.bottomAnchor.constraint(equalTo: bottomAnchor)
        ])
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    func configure(title: String, voiceEnabled: Bool, active: Bool, liveDrawing: Bool, onTap: @escaping () -> Void,
                   onBegin: @escaping () -> Void, onCancelChange: @escaping (Bool) -> Void, onEnd: @escaping (Bool) -> Void) {
        control.title.text = title
        control.voiceEnabled = voiceEnabled
        control.onTap = onTap; control.onBegin = onBegin; control.onCancelChange = onCancelChange; control.onEnd = onEnd
        control.accessibilityLabel = liveDrawing ? "边说边画" : "输入想法"
        control.accessibilityValue = active ? title : ""
        control.accessibilityHint = liveDrawing ? "轻点打字；按住说话时画布会变化，松开后确认保留或放弃，上滑取消" : "轻点打字；按住听写，松开后可编辑草稿，上滑取消"
        control.icon.image = UIImage(systemName: active ? "waveform" : "mic.fill")
        control.icon.backgroundColor = active ? UIColor(red: 0.66, green: 0.30, blue: 0.20, alpha: 1) : UIColor(red: 0.14, green: 0.19, blue: 0.14, alpha: 1)
    }
    func cancelIfNeeded() { control.cancelIfNeeded() }
}

private final class HoldToTalkButton: UIControl, UIGestureRecognizerDelegate {
    let title = UILabel()
    let icon = UIImageView()
    var voiceEnabled = true
    var onTap: (() -> Void)?
    var onBegin: (() -> Void)?
    var onCancelChange: ((Bool) -> Void)?
    var onEnd: ((Bool) -> Void)?
    private var holding = false
    private var cancelling = false
    override init(frame: CGRect) {
        super.init(frame: frame)
        isAccessibilityElement = true; accessibilityTraits = .button; accessibilityIdentifier = "chatButton"
        title.font = UIFont.preferredFont(forTextStyle: .body)
        title.adjustsFontForContentSizeCategory = true
        title.textColor = CanvasStyle.ink
        title.adjustsFontSizeToFitWidth = true; title.minimumScaleFactor = 0.8
        icon.tintColor = .white; icon.contentMode = .center; icon.layer.cornerRadius = 21
        icon.preferredSymbolConfiguration = UIImage.SymbolConfiguration(pointSize: 19, weight: .medium)
        title.translatesAutoresizingMaskIntoConstraints = false; icon.translatesAutoresizingMaskIntoConstraints = false
        addSubview(title); addSubview(icon)
        NSLayoutConstraint.activate([
            title.leadingAnchor.constraint(equalTo: leadingAnchor), title.centerYAnchor.constraint(equalTo: centerYAnchor),
            title.trailingAnchor.constraint(lessThanOrEqualTo: icon.leadingAnchor, constant: -12),
            icon.trailingAnchor.constraint(equalTo: trailingAnchor), icon.centerYAnchor.constraint(equalTo: centerYAnchor),
            icon.widthAnchor.constraint(equalToConstant: 42), icon.heightAnchor.constraint(equalToConstant: 42)
        ])
        let hold = UILongPressGestureRecognizer(target: self, action: #selector(hold(_:)))
        hold.minimumPressDuration = 0.3; hold.allowableMovement = 30; hold.delegate = self
        let tap = UITapGestureRecognizer(target: self, action: #selector(tap))
        tap.require(toFail: hold)
        addGestureRecognizer(hold); addGestureRecognizer(tap)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override func accessibilityActivate() -> Bool { onTap?(); return true }
    override func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
        !(gestureRecognizer is UILongPressGestureRecognizer) || voiceEnabled
    }
    @objc private func tap() { onTap?() }
    @objc private func hold(_ gesture: UILongPressGestureRecognizer) {
        switch gesture.state {
        case .began:
            holding = true; cancelling = false
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            onBegin?()
        case .changed:
            let cancel = gesture.location(in: self).y < -35
            if cancel != cancelling { cancelling = cancel; onCancelChange?(cancel) }
        case .ended:
            let cancelled = cancelling
            holding = false; cancelling = false
            onEnd?(cancelled)
        case .cancelled, .failed: cancelIfNeeded()
        default: break
        }
    }
    func cancelIfNeeded() {
        guard holding else { return }
        holding = false; cancelling = false; onEnd?(true)
    }
}
