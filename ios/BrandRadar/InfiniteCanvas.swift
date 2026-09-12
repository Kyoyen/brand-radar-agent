import SwiftUI

struct InfiniteCanvas: UIViewRepresentable {
    @ObservedObject var store: BoardStore
    var onOpen: (String) -> Void
    func makeUIView(context: Context) -> RadarCanvasView {
        let view = RadarCanvasView()
        view.onCommand = { store.performCanvasCommand($0) }
        view.onSelection = { store.tapCard($0) }
        view.onDragSelection = { store.selectedCardID = $0 }
        view.onOpen = onOpen
        view.onMove = { store.moveCard($0, x: $1, y: $2) }
        view.onMoveGroup = { store.moveGroup($0, dx: $1, dy: $2) }
        view.onViewport = { x, y, zoom in store.update { $0.offsetX = x; $0.offsetY = y; $0.zoom = zoom } }
        return view
    }
    func updateUIView(_ view: RadarCanvasView, context: Context) {
        view.configure(board: store.current, selection: store.selectedCardID, fitRequest: store.fitRequest)
    }
}

final class RadarCanvasView: UIView, UIGestureRecognizerDelegate {
    var onCommand: ((CanvasCommand) -> Void)?
    var onSelection: ((String?) -> Void)?
    var onDragSelection: ((String) -> Void)?
    var onOpen: ((String) -> Void)?
    var onMove: ((String, Double, Double) -> Void)?
    var onMoveGroup: ((String, Double, Double) -> Void)?
    var onViewport: ((Double, Double, Double) -> Void)?
    private var board: RadarBoard?
    private var selection: String?
    private var scale: CGFloat = 0.67
    private var translation = CGPoint(x: 28, y: 120)
    private var dragID: String?
    private var dragGroupID: String?
    private var groupOrigins: [String: CGPoint] = [:]
    private var dragOrigin = CGPoint.zero
    private var gestureStart = CGPoint.zero
    private var lastTapID: String?
    private var lastTapTime: TimeInterval = 0
    private var doubleTapObjectID: String?
    private var panOrigin = CGPoint.zero
    private var pinchOrigin: CGFloat = 1
    private var pinchWorld = CGPoint.zero
    private var fitVersion = 0
    private var needsFit = false
    private var interacting = false
    private var selectedIDs = Set<String>()
    private var multiSelect = false
    private var connectionSource: String?
    private var connectionPoint: CGPoint?
    private var connectionTarget: String?
    private var resizingID: String?
    private var resizeOrigin = CGSize.zero
    private var selectionStart: CGPoint?
    private var selectionBox: CGRect?
    private let toolbar = UIStackView()
    private let multiButton = UIButton(type: .system)
    private var newIDs = Set<String>()
    private let locateButton = UIButton(type: .system)
    private var lastObjectIDs = Set<String>()
    private var appearanceTimes: [String: TimeInterval] = [:]
    private var animationTimer: Timer?

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = UIColor(red: 0.956, green: 0.955, blue: 0.925, alpha: 1)
        accessibilityIdentifier = "canvas"
        isMultipleTouchEnabled = true
        let pan = CanvasPanGestureRecognizer(target: self, action: #selector(pan(_:)))
        pan.maximumNumberOfTouches = 1; pan.delegate = self
        toolbar.axis = .horizontal; toolbar.spacing = 8; toolbar.alignment = .center
        toolbar.backgroundColor = UIColor.systemBackground.withAlphaComponent(0.96)
        toolbar.layer.cornerRadius = 16; toolbar.isLayoutMarginsRelativeArrangement = true
        toolbar.layoutMargins = UIEdgeInsets(top: 8, left: 12, bottom: 8, right: 12)
        addSubview(toolbar)
        multiButton.setImage(UIImage(systemName: "checkmark.circle"), for: .normal)
        multiButton.backgroundColor = UIColor.systemBackground.withAlphaComponent(0.95)
        multiButton.layer.cornerRadius = 22; multiButton.accessibilityLabel = "多选"
        multiButton.accessibilityIdentifier = "canvasMultiSelect"
        multiButton.addTarget(self, action: #selector(toggleMulti), for: .touchUpInside); addSubview(multiButton)
        locateButton.setTitle("查看新增", for: .normal); locateButton.titleLabel?.font = .systemFont(ofSize: 13, weight: .medium)
        locateButton.backgroundColor = .systemBackground; locateButton.layer.cornerRadius = 18
        locateButton.addTarget(self, action: #selector(locateNew), for: .touchUpInside); locateButton.isHidden = true; addSubview(locateButton)
        addGestureRecognizer(pan)
        let pinch = UIPinchGestureRecognizer(target: self, action: #selector(pinch(_:)))
        pinch.delegate = self; addGestureRecognizer(pinch)
        let tap = UITapGestureRecognizer(target: self, action: #selector(tap(_:)))
        tap.delegate = self; addGestureRecognizer(tap)
        // Select on the first tap; a rapid second tap opens only the same object.
        let hold = UILongPressGestureRecognizer(target: self, action: #selector(hold(_:)))
        hold.minimumPressDuration = 0.5; hold.delegate = self; addGestureRecognizer(hold)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    func configure(board: RadarBoard, selection: String?, fitRequest: Int) {
        let changed = self.board?.id != board.id
        let dragged = dragID.flatMap { id in self.board?.cards.first { $0.id == id } }
        let draggedMembers = self.board?.cards.filter { groupOrigins[$0.id] != nil } ?? []
        let currentIDs = Set(board.visibleCards.map(\.id) + (board.groups ?? []).map(\.id))
        if !changed {
            let additions = currentIDs.subtracting(lastObjectIDs)
            newIDs.formUnion(additions)
            let oldEdges = Set(self.board?.edges.map(\.id) ?? [])
            if !UIAccessibility.isReduceMotionEnabled {
                for id in additions.union(Set(board.edges.map(\.id)).subtracting(oldEdges)) { appearanceTimes[id] = Date.timeIntervalSinceReferenceDate }
                if !appearanceTimes.isEmpty { startAppearanceAnimation() }
            }
        } else { newIDs = []; selectedIDs = []; connectionSource = nil; multiSelect = false }
        lastObjectIDs = currentIDs
        self.board = board
        if self.selection != selection, let selection { selectedIDs = [selection] }
        self.selection = selection
        selectedIDs = selectedIDs.filter { currentIDs.contains($0) || board.edges.map(\.id).contains($0) }

        if !changed, let dragged, let i = self.board?.cards.firstIndex(where: { $0.id == dragged.id }) {
            self.board?.cards[i].x = dragged.x; self.board?.cards[i].y = dragged.y
        }
        if !changed {
            for card in draggedMembers {
                if let i = self.board?.cards.firstIndex(where: { $0.id == card.id }) {
                    self.board?.cards[i].x = card.x; self.board?.cards[i].y = card.y
                }
            }
        } else { dragID = nil; dragGroupID = nil; groupOrigins = [:] }
        if changed { scale = board.zoom; translation = CGPoint(x: board.offsetX, y: board.offsetY) }
        if fitRequest != fitVersion {
            fitVersion = fitRequest
            if bounds.width > 0 && !interacting { fit() } else { needsFit = true }
        }
        setNeedsDisplay(); refreshAccessibility(); updateToolbar()
    }
    override func layoutSubviews() {
        super.layoutSubviews()
        if needsFit && bounds.width > 0 && !interacting { needsFit = false; fit() }
        toolbar.frame = CGRect(x: 16, y: max(140, safeAreaInsets.top + 88), width: min(bounds.width - 32, toolbar.systemLayoutSizeFitting(UIView.layoutFittingCompressedSize).width), height: 46)
        multiButton.frame = CGRect(x: bounds.width - 60, y: bounds.height - safeAreaInsets.bottom - 195, width: 44, height: 44)
        locateButton.frame = CGRect(x: 16, y: bounds.height - safeAreaInsets.bottom - 195, width: 100, height: 36)
        refreshAccessibility()
    }
    private func world(_ point: CGPoint) -> CGPoint {
        CGPoint(x: (point.x - translation.x) / scale, y: (point.y - translation.y) / scale)
    }
    private func cardRect(_ card: RadarCard) -> CGRect { CanvasGeometry.cardRect(card) }
    private func groupRect(_ group: RadarGroup) -> CGRect? { board.flatMap { CanvasGeometry.groupRect(group, in: $0) } }
    private var hiddenIDs: Set<String> { board.map { CanvasGeometry.hiddenIDs(in: $0) } ?? [] }
    private func objectRect(_ id: String) -> CGRect? { board.flatMap { CanvasGeometry.rect(id, in: $0) } }
    private func hitGroup(_ point: CGPoint) -> RadarGroup? {
        let p = world(point)
        return board?.groups?.reversed().first {
            guard !hiddenIDs.contains($0.id), let rect = groupRect($0) else { return false }
            return CGRect(x: rect.minX, y: rect.minY, width: rect.width, height: $0.collapsed == true ? rect.height : 48).contains(p)
        }
    }
    private func hit(_ point: CGPoint) -> RadarCard? {
        let p = world(point)
        return board?.visibleCards.reversed().first { !hiddenIDs.contains($0.id) && cardRect($0).contains(p) }
    }
    private func hitObject(_ point: CGPoint) -> String? { hit(point)?.id ?? hitGroup(point)?.id }
    private func visibleEndpoint(_ id: String) -> String? {
        guard hiddenIDs.contains(id), let board else { return id }
        var current = id, visited = Set<String>()
        while visited.insert(current).inserted {
            guard let parent = board.groups?.first(where: { $0.cardIDs.contains(current) || ($0.groupIDs ?? []).contains(current) }) else { return nil }
            if !hiddenIDs.contains(parent.id) { return parent.id }
            current = parent.id
        }
        return nil
    }
    private func edgeGeometry(_ edge: RadarEdge) -> (UIBezierPath, CGPoint, CGPoint, CGPoint)? {
        guard let from = visibleEndpoint(edge.fromID), let to = visibleEndpoint(edge.toID), from != to, let a = objectRect(from), let b = objectRect(to) else { return nil }
        return CanvasGeometry.curve(from: a, to: b)
    }
    private func hitEdge(_ point: CGPoint) -> RadarEdge? {
        board?.edges.reversed().first { edge in
            guard let curve = edgeGeometry(edge) else { return false }
            return curve.0.cgPath.copy(strokingWithWidth: max(18, 24 / scale), lineCap: .round, lineJoin: .round, miterLimit: 0).contains(world(point))
        }
    }
    private func port(_ id: String) -> CGPoint? { objectRect(id).map { CGPoint(x: $0.maxX, y: $0.midY) } }
    private func handleHit(_ p: CGPoint, portMode: Bool) -> String? {
        selectedIDs.first { id in
            guard let r = objectRect(id) else { return false }
            let h = portMode ? CGPoint(x: r.maxX, y: r.midY) : CGPoint(x: r.maxX, y: r.maxY)
            let other = portMode ? CGPoint(x: r.maxX, y: r.maxY) : CGPoint(x: r.maxX, y: r.midY)
            let distance = hypot(world(p).x-h.x, world(p).y-h.y)
            return distance < max(14, 22 / scale) && distance <= hypot(world(p).x-other.x, world(p).y-other.y)
        }
    }
    private func saveViewport() { onViewport?(translation.x, translation.y, scale) }
    func fit() {
        guard !interacting else { needsFit = true; return }
        let rects = (board?.visibleCards.filter { !hiddenIDs.contains($0.id) }.map(cardRect) ?? []) + (board?.groups?.filter { !hiddenIDs.contains($0.id) }.compactMap(groupRect) ?? [])
        guard let first = rects.first else {
            scale = 0.8; translation = CGPoint(x: 24, y: 180); setNeedsDisplay()
            DispatchQueue.main.async { [weak self] in self?.saveViewport() }
            return
        }
        let rect = rects.dropFirst().reduce(first) { $0.union($1) }
        fit(rect)
    }
    private func fit(_ rect: CGRect) {
        let space = CGRect(x: 24, y: 180, width: max(100, bounds.width - 48), height: max(160, bounds.height - 430))
        scale = max(0.0001, min(1, min(space.width / rect.width, space.height / rect.height)))
        translation = CGPoint(x: space.midX - rect.midX * scale, y: space.midY - rect.midY * scale)
        setNeedsDisplay()
        // Never publish SwiftUI state from updateUIView's rendering pass.
        DispatchQueue.main.async { [weak self] in self?.saveViewport() }
    }
    @objc private func tap(_ gesture: UITapGestureRecognizer) {
        let point = gesture.location(in: self)
        if let group = hitGroup(point), let rect = groupRect(group), world(point).x > rect.maxX - 48 {
            onCommand?(.collapse(id: group.id)); return
        }
        if let source = connectionSource {
            if let target = hitObject(point), source != target { onCommand?(.connect(from: source, to: target)); connectionSource = nil; updateToolbar() }
            else if hitObject(point) == nil { offerConnectedNode(source: source, at: world(point)) }
            return
        }
        let id = hitObject(point) ?? hitEdge(point)?.id
        let now = Date.timeIntervalSinceReferenceDate
        doubleTapObjectID = id == lastTapID && now - lastTapTime < 0.45 ? id : nil
        lastTapID = id; lastTapTime = now
        if !multiSelect, doubleTapObjectID != nil {
            open(gesture); lastTapTime = 0; return
        }
        if multiSelect, let id {
            if selectedIDs.contains(id) { selectedIDs.remove(id) } else { selectedIDs.insert(id) }
        } else { selectedIDs = id.map { [$0] } ?? []; selection = hitObject(point); onSelection?(selection) }
        updateToolbar(); setNeedsDisplay(); UISelectionFeedbackGenerator().selectionChanged()
    }
    @objc private func open(_ gesture: UITapGestureRecognizer) {
        guard !multiSelect, let id = doubleTapObjectID, id == hitObject(gesture.location(in: self)) || id == hitEdge(gesture.location(in: self))?.id else { return }
        if let card = hit(gesture.location(in: self)) { selectCard(card.id); onOpen?(card.id) }
        else if let group = hitGroup(gesture.location(in: self)), let rect = groupRect(group) { fit(rect) }
        else if let edge = hitEdge(gesture.location(in: self)) { editEdge(edge) }
    }
    private func selectCard(_ id: String) { selection = id; selectedIDs = [id]; onSelection?(id); updateToolbar() }
    @objc private func hold(_ gesture: UILongPressGestureRecognizer) {
        guard gesture.state == .began, let card = hit(gesture.location(in: self)) else { return }
        selectCard(card.id); onOpen?(card.id)
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
    @objc private func pan(_ gesture: UIPanGestureRecognizer) {
        let location = gesture.location(in: self)
        let point = (gesture as? CanvasPanGestureRecognizer)?.initialPoint ?? gestureStart
        let delta = CGPoint(x: location.x - point.x, y: location.y - point.y)
        switch gesture.state {
        case .began:
            interacting = true
            gestureStart = point
            panOrigin = translation; groupOrigins = [:]
            if let id = handleHit(point, portMode: true) { connectionSource = id; connectionPoint = world(location) }
            else if let id = handleHit(point, portMode: false), let rect = objectRect(id) { resizingID = id; resizeOrigin = rect.size }
            else if multiSelect, hitObject(point) == nil { selectionStart = world(point); selectionBox = CGRect(origin: world(point), size: .zero) }
            else if let id = hitObject(point), let board {
                if !selectedIDs.contains(id) { selectedIDs = [id] }
                dragID = id
                selection = id; onDragSelection?(id)
                var members = selectedIDs
                for group in board.groups ?? [] where selectedIDs.contains(group.id) { members.formUnion(CanvasGeometry.descendants(group, in: board)) }
                for card in board.visibleCards where members.contains(card.id) { groupOrigins[card.id] = CGPoint(x: card.x, y: card.y) }
            }
            updateToolbar()
        case .changed:
            if resizingID != nil { setNeedsDisplay() }
            else if connectionSource != nil {
                connectionPoint = world(gesture.location(in: self)); connectionTarget = hitObject(gesture.location(in: self))
                if connectionTarget == connectionSource { connectionTarget = nil }
            } else if let start = selectionStart {
                let end = world(gesture.location(in: self)); selectionBox = CGRect(x: min(start.x,end.x), y: min(start.y,end.y), width: abs(start.x-end.x), height: abs(start.y-end.y))
            } else if dragID != nil {
                for i in board?.cards.indices ?? 0..<0 {
                    guard let id = board?.cards[i].id, let origin = groupOrigins[id] else { continue }
                    board?.cards[i].x = origin.x + delta.x / scale; board?.cards[i].y = origin.y + delta.y / scale
                }
            } else { translation = CGPoint(x: panOrigin.x + delta.x, y: panOrigin.y + delta.y) }
            if let id = resizingID {
                if let i = board?.cards.firstIndex(where: { $0.id == id }) {
                    board?.cards[i].width = max(180, min(900, resizeOrigin.width + delta.x / scale))
                    board?.cards[i].height = max(150, min(1800, resizeOrigin.height + delta.y / scale))
                } else if let i = board?.groups?.firstIndex(where: { $0.id == id }) {
                    board?.groups?[i].width = max(230, resizeOrigin.width + delta.x / scale)
                    board?.groups?[i].height = max(88, resizeOrigin.height + delta.y / scale)
                }
            }
            setNeedsDisplay()
        case .ended, .cancelled:
            if gesture.state == .ended {
                if let id = resizingID { onCommand?(.resize(id: id, width: max(180, resizeOrigin.width + delta.x / scale), height: max(150, resizeOrigin.height + delta.y / scale))) }
                else if let source = connectionSource, connectionPoint != nil {
                    if let target = connectionTarget { onCommand?(.connect(from: source, to: target)); connectionSource = nil }
                    else { offerConnectedNode(source: source, at: world(gesture.location(in: self))) }
                } else if let box = selectionBox {
                    for card in board?.visibleCards ?? [] where !hiddenIDs.contains(card.id) && box.intersects(cardRect(card)) { selectedIDs.insert(card.id) }
                    for group in board?.groups ?? [] where !hiddenIDs.contains(group.id) { if let rect = groupRect(group), box.contains(rect) { selectedIDs.insert(group.id) } }
                } else if dragID != nil { onCommand?(.move(ids: selectedIDs, dx: delta.x / scale, dy: delta.y / scale)) }
                else { saveViewport() }
            }
            dragID = nil; dragGroupID = nil; groupOrigins = [:]; resizingID = nil; selectionStart = nil; selectionBox = nil; connectionPoint = nil; connectionTarget = nil; interacting = false
            if needsFit { needsFit = false; fit() }
            refreshAccessibility(); updateToolbar(); setNeedsDisplay()
        default: break
        }
    }
    @objc private func pinch(_ gesture: UIPinchGestureRecognizer) {
        let point = gesture.location(in: self)
        switch gesture.state {
        case .began: interacting = true; pinchOrigin = scale; pinchWorld = world(point)
        case .changed:
            scale = max(0.0001, min(2.5, pinchOrigin * gesture.scale))
            translation = CGPoint(x: point.x - pinchWorld.x * scale, y: point.y - pinchWorld.y * scale)
            setNeedsDisplay()
        case .ended, .cancelled:
            saveViewport(); interacting = false
            if needsFit { needsFit = false; fit() }
            refreshAccessibility()
        default: break
        }
    }
    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool {
        var view = touch.view
        while let current = view, current !== self { if current is UIControl { return false }; view = current.superview }
        return true
    }
    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer) -> Bool { false }
    override func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
        if gestureRecognizer is UILongPressGestureRecognizer { return hit(gestureRecognizer.location(in: self)) != nil }
        let point = gestureRecognizer.location(in: self)
        if toolbar.frame.contains(point) && !toolbar.isHidden || multiButton.frame.contains(point) || !locateButton.isHidden && locateButton.frame.contains(point) { return false }
        return true
    }

    override func draw(_ rect: CGRect) {
        guard let context = UIGraphicsGetCurrentContext() else { return }
        let gap = max(14, 28 * scale)
        context.setFillColor(UIColor.black.withAlphaComponent(0.12).cgColor)
        let startX = translation.x.truncatingRemainder(dividingBy: gap)
        let startY = translation.y.truncatingRemainder(dividingBy: gap)
        for x in stride(from: startX, to: bounds.width, by: gap) {
            for y in stride(from: startY, to: bounds.height, by: gap) { context.fillEllipse(in: CGRect(x: x, y: y, width: 1.5, height: 1.5)) }
        }
        context.saveGState()
        context.translateBy(x: translation.x, y: translation.y); context.scaleBy(x: scale, y: scale)
        guard let board else { context.restoreGState(); return }
        let cards = board.visibleCards
        for group in (board.groups ?? []).sorted(by: { (groupRect($0)?.width ?? 0) * (groupRect($0)?.height ?? 0) > (groupRect($1)?.width ?? 0) * (groupRect($1)?.height ?? 0) }) where !hiddenIDs.contains(group.id) { drawGroup(group) }
        for edge in board.edges {
            drawEdge(edge, context: context)
        }
        let visibleWorld = CGRect(x: -translation.x / scale, y: -translation.y / scale, width: bounds.width / scale, height: bounds.height / scale).insetBy(dx: -40, dy: -40)
        for card in cards where !hiddenIDs.contains(card.id) && cardRect(card).intersects(visibleWorld) { drawCard(card, context: context) }
        for id in selectedIDs { drawHandles(id) }
        if let target = connectionTarget, let rect = objectRect(target) { UIColor.systemGreen.setStroke(); let p = UIBezierPath(roundedRect: rect.insetBy(dx: -5, dy: -5), cornerRadius: 22); p.lineWidth = 3; p.stroke() }
        if let source = connectionSource, let start = port(source), let end = connectionPoint { let p = UIBezierPath(); p.move(to: start); p.addLine(to: end); p.lineWidth = 2; UIColor.systemGreen.setStroke(); p.stroke() }
        if let box = selectionBox { UIColor.systemGreen.withAlphaComponent(0.1).setFill(); UIColor.systemGreen.setStroke(); let p = UIBezierPath(rect: box); p.lineWidth = 1 / scale; p.fill(); p.stroke() }
        context.restoreGState()
    }
    private func drawGroup(_ group: RadarGroup) {
        let context = UIGraphicsGetCurrentContext(); context?.saveGState(); context?.setAlpha(appearance(group.id)); defer { context?.restoreGState() }
        guard let rect = groupRect(group) else { return }
        let color = RadarCard(title: "", body: "", color: group.color).uiColor
        let path = UIBezierPath(roundedRect: rect, cornerRadius: 28)
        color.withAlphaComponent(0.32).setFill(); path.fill()
        UIColor(red: 0.35, green: 0.43, blue: 0.35, alpha: 0.28).setStroke()
        path.lineWidth = selectedIDs.contains(group.id) ? 3 : 1.5; path.stroke()
        text(group.title, CGRect(x: rect.minX + 23, y: rect.minY + 17, width: rect.width - 70, height: 25), .systemFont(ofSize: 18, weight: .semibold), .darkGray)
        text(group.collapsed == true ? "+" : "−", CGRect(x: rect.maxX - 35, y: rect.minY + 15, width: 22, height: 26), .systemFont(ofSize: 22), .gray)
    }
    private func drawEdge(_ edge: RadarEdge, context: CGContext) {
        guard let (path, start, end, c2) = edgeGeometry(edge) else { return }
        let highlighted = selectedIDs.contains(edge.id) || selectedIDs.contains(edge.fromID) || selectedIDs.contains(edge.toID)
        context.saveGState(); context.setAlpha(appearance(edge.id))
        defer { context.restoreGState() }
        UIColor(red: 0.25, green: 0.40, blue: 0.28, alpha: highlighted ? 1 : 0.7).setStroke()
        let progress = appearance(edge.id)
        if progress < 1 {
            let c1 = CGPoint(x: start.x + end.x - c2.x, y: start.y + end.y - c2.y)
            let growing = UIBezierPath(); growing.move(to: start)
            for step in 1...24 {
                let t = CGFloat(step) / 24 * progress, u = 1 - t
                growing.addLine(to: CGPoint(x: u*u*u*start.x + 3*u*u*t*c1.x + 3*u*t*t*c2.x + t*t*t*end.x, y: u*u*u*start.y + 3*u*u*t*c1.y + 3*u*t*t*c2.y + t*t*t*end.y))
            }
            growing.lineWidth = highlighted ? 3.5 : 2; growing.stroke()
        } else { path.lineWidth = highlighted ? 3.5 : 2; path.stroke() }
        if edge.directed != false && progress >= 1 {
            let angle = atan2(end.y - c2.y, end.x - c2.x)
            let arrow = UIBezierPath(); arrow.move(to: CGPoint(x: end.x - 10 * cos(angle - 0.45), y: end.y - 10 * sin(angle - 0.45))); arrow.addLine(to: end); arrow.addLine(to: CGPoint(x: end.x - 10 * cos(angle + 0.45), y: end.y - 10 * sin(angle + 0.45))); arrow.lineWidth = 2; arrow.stroke()
        }
        if !edge.label.isEmpty {
            let middle = CGPoint(x: (start.x + end.x) / 2, y: (start.y + end.y) / 2)
            let font = UIFont.systemFont(ofSize: 11, weight: .medium)
            let size = (edge.label as NSString).size(withAttributes: [.font: font])
            let box = CGRect(x: middle.x - min(size.width, 120) / 2 - 9, y: middle.y - 11, width: min(size.width, 120) + 18, height: 23)
            backgroundColor?.setFill(); UIBezierPath(roundedRect: box, cornerRadius: 10).fill()
            text(edge.label, box.insetBy(dx: 9, dy: 4), font, UIColor.darkGray)
        }
    }
    private func drawCard(_ card: RadarCard, context: CGContext) {
        context.saveGState(); context.setAlpha(appearance(card.id)); defer { context.restoreGState() }
        let rect = cardRect(card)
        let path = UIBezierPath(roundedRect: rect, cornerRadius: 19)
        context.saveGState(); context.setShadow(offset: CGSize(width: 0, height: 5), blur: 16, color: UIColor.black.withAlphaComponent(0.06).cgColor)
        card.uiColor.setFill(); path.fill(); context.restoreGState()
        (selectedIDs.contains(card.id) ? UIColor(red: 0.2, green: 0.36, blue: 0.21, alpha: 1) : UIColor.black.withAlphaComponent(0.07)).setStroke()
        path.lineWidth = selectedIDs.contains(card.id) ? 3 : 1; path.stroke()
        let secondary = UIColor(red: 0.3, green: 0.34, blue: 0.28, alpha: 1)
        text(card.title, CGRect(x: rect.minX + 22, y: rect.minY + 26, width: rect.width - 44, height: 60), .systemFont(ofSize: 23, weight: .semibold), .black)
        text(card.effectiveBlocks.map(\.summary).joined(separator: "\n"), CGRect(x: rect.minX + 22, y: rect.minY + 96, width: rect.width - 44, height: max(28, rect.height - 139)), .systemFont(ofSize: 14), secondary)
        if let attachment = card.effectiveBlocks.first(where: { $0.kind == "image" || $0.kind == "drawing" })?.attachment, let image = CanvasAssets.shared.thumbnail(for: attachment) {
            let thumbnail = CGRect(x: rect.minX + 22, y: rect.minY + 96, width: rect.width - 44, height: max(40, rect.height - 139))
            context.saveGState(); UIBezierPath(roundedRect: thumbnail, cornerRadius: 8).addClip()
            let ratio = min(thumbnail.width / image.size.width, thumbnail.height / image.size.height)
            let size = CGSize(width: image.size.width * ratio, height: image.size.height * ratio)
            card.uiColor.setFill(); context.fill(thumbnail)
            image.draw(in: CGRect(x: thumbnail.midX - size.width / 2, y: thumbnail.midY - size.height / 2, width: size.width, height: size.height)); context.restoreGState()
        }
        context.setStrokeColor(UIColor.black.withAlphaComponent(0.08).cgColor); context.setLineWidth(1)
        context.move(to: CGPoint(x: rect.minX + 22, y: rect.maxY - 31)); context.addLine(to: CGPoint(x: rect.maxX - 22, y: rect.maxY - 31)); context.strokePath()
        text(card.status == "kept" ? "✓ 已采用" : "↗", CGRect(x: rect.minX + 22, y: rect.maxY - 24, width: rect.width - 44, height: 15), .systemFont(ofSize: 10, weight: .medium), secondary)
    }
    private func appearance(_ id: String) -> CGFloat {
        guard let time = appearanceTimes[id] else { return 1 }
        return max(0.1, min(1, (Date.timeIntervalSinceReferenceDate - time) / 0.24))
    }
    private func startAppearanceAnimation() {
        guard animationTimer == nil else { return }
        animationTimer = Timer.scheduledTimer(withTimeInterval: 1 / 60, repeats: true) { [weak self] timer in
            guard let self else { timer.invalidate(); return }
            let now = Date.timeIntervalSinceReferenceDate
            self.appearanceTimes = self.appearanceTimes.filter { now - $0.value < 0.24 }
            self.setNeedsDisplay()
            if self.appearanceTimes.isEmpty { timer.invalidate(); self.animationTimer = nil }
        }
    }
    private func drawHandles(_ id: String) {
        guard let r = objectRect(id) else { return }
        let radius = max(7, 10 / scale)
        UIColor.white.setFill(); UIColor.systemGreen.setStroke()
        let port = UIBezierPath(ovalIn: CGRect(x: r.maxX-radius, y: r.midY-radius, width: radius*2, height: radius*2)); port.lineWidth = 2 / scale; port.fill(); port.stroke()
        let handle = UIBezierPath(roundedRect: CGRect(x: r.maxX-radius, y: r.maxY-radius, width: radius*2, height: radius*2), cornerRadius: 3 / scale); handle.lineWidth = 2 / scale; handle.fill(); handle.stroke()
    }
    @objc private func toggleMulti() {
        multiSelect.toggle(); connectionSource = nil
        if !multiSelect { selectedIDs = []; selection = nil; onSelection?(nil) }
        updateToolbar(); setNeedsDisplay()
    }
    @objc private func locateNew() {
        guard let rect = newIDs.compactMap(objectRect).reduce(nil as CGRect?, { $0?.union($1) ?? $1 }) else { return }
        fit(rect); newIDs = []; locateButton.isHidden = true
    }
    private func updateToolbar() {
        toolbar.arrangedSubviews.forEach { toolbar.removeArrangedSubview($0); $0.removeFromSuperview() }
        multiButton.tintColor = multiSelect ? .systemGreen : .darkGray
        toolbar.isHidden = selectedIDs.isEmpty && !multiSelect && connectionSource == nil
        func button(_ title: String, symbol: String, _ action: @escaping () -> Void) {
            let b = UIButton(type: .system)
            b.setImage(UIImage(systemName: symbol), for: .normal); b.tintColor = .darkGray
            b.accessibilityLabel = title; b.accessibilityIdentifier = title == "编辑" ? "editCardButton" : "canvas_" + title
            b.widthAnchor.constraint(equalToConstant: 36).isActive = true
            b.heightAnchor.constraint(equalToConstant: 32).isActive = true
            b.addAction(UIAction { _ in action() }, for: .touchUpInside); toolbar.addArrangedSubview(b)
        }
        if connectionSource != nil {
            let label = UILabel(); label.text = "点选要连接的对象"; label.font = .systemFont(ofSize: 13); toolbar.addArrangedSubview(label)
            button("取消连接", symbol: "xmark") { [weak self] in self?.connectionSource = nil; self?.updateToolbar(); self?.setNeedsDisplay() }
        } else if selectedIDs.count == 1, let id = selectedIDs.first {
            if let edge = board?.edges.first(where: { $0.id == id }) {
                button("编辑连线", symbol: "pencil") { [weak self] in self?.editEdge(edge) }
                button("反转连线", symbol: "arrow.left.arrow.right") { [weak self] in self?.onCommand?(.edge(id: id, label: edge.label, directed: edge.directed != false, reversed: true)) }
            } else {
                if board?.cards.contains(where: { $0.id == id }) == true {
                    button("编辑", symbol: "pencil") { [weak self] in self?.onOpen?(id) }
                } else {
                    button("重命名", symbol: "pencil") { [weak self] in self?.rename(id) }
                    button("解散分组", symbol: "rectangle.3.group") { [weak self] in self?.onCommand?(.ungroup(id: id)); self?.selectedIDs = []; self?.updateToolbar() }
                }
                button("连接", symbol: "arrow.up.right") { [weak self] in self?.connectionSource = id; self?.updateToolbar() }
                button("复制", symbol: "plus.square.on.square") { [weak self] in self?.onCommand?(.duplicate(ids: [id])) }
            }
            button("删除", symbol: "trash") { [weak self] in self?.deleteSelection() }
        } else if !selectedIDs.isEmpty {
            button("分组", symbol: "rectangle.3.group") { [weak self] in guard let self else { return }; self.onCommand?(.group(ids: self.selectedIDs)); self.selectedIDs = []; self.updateToolbar() }
            button("复制", symbol: "plus.square.on.square") { [weak self] in guard let self else { return }; self.onCommand?(.duplicate(ids: self.selectedIDs)) }
            button("删除", symbol: "trash") { [weak self] in self?.deleteSelection() }
        } else if multiSelect {
            let label = UILabel(); label.text = "点选或拖动框选"; label.font = .systemFont(ofSize: 13); toolbar.addArrangedSubview(label)
        }
        let viewport = CGRect(x: -translation.x / scale, y: (160-translation.y) / scale, width: bounds.width / scale, height: max(1,bounds.height-360) / scale)
        locateButton.isHidden = !newIDs.contains { objectRect($0).map { !viewport.intersects($0) } ?? false }
        setNeedsLayout()
    }
    private var presenter: UIViewController? {
        var responder: UIResponder? = self
        while let next = responder?.next { if let vc = next as? UIViewController { return vc }; responder = next }
        return nil
    }
    private func show(_ alert: UIAlertController) {
        alert.popoverPresentationController?.sourceView = self
        alert.popoverPresentationController?.sourceRect = toolbar.frame
        presenter?.present(alert, animated: !UIAccessibility.isReduceMotionEnabled)
    }
    private func offerConnectedNode(source: String, at point: CGPoint) {
        let alert = UIAlertController(title: nil, message: nil, preferredStyle: .actionSheet)
        alert.addAction(UIAlertAction(title: "新建节点", style: .default) { [weak self] _ in
            self?.onCommand?(.createConnected(from: source, x: point.x, y: point.y)); self?.connectionSource = nil; self?.updateToolbar()
        })
        alert.addAction(UIAlertAction(title: "取消", style: .cancel) { [weak self] _ in self?.connectionSource = nil; self?.updateToolbar() })
        show(alert)
    }
    private func rename(_ id: String) {
        let alert = UIAlertController(title: "名称", message: nil, preferredStyle: .alert)
        alert.addTextField { $0.text = self.board?.groups?.first(where: { $0.id == id })?.title ?? self.board?.cards.first(where: { $0.id == id })?.title }
        alert.addAction(UIAlertAction(title: "取消", style: .cancel))
        alert.addAction(UIAlertAction(title: "保存", style: .default) { [weak self] _ in
            guard let title = alert.textFields?.first?.text, !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
            self?.onCommand?(.rename(id: id, title: title))
        }); show(alert)
    }
    private func editEdge(_ edge: RadarEdge) {
        let alert = UIAlertController(title: "关系", message: nil, preferredStyle: .alert)
        alert.addTextField { $0.text = edge.label; $0.placeholder = "关系说明" }
        alert.addAction(UIAlertAction(title: "保存", style: .default) { [weak self] _ in self?.onCommand?(.edge(id: edge.id, label: alert.textFields?.first?.text ?? "", directed: edge.directed != false, reversed: false)) })
        alert.addAction(UIAlertAction(title: edge.directed == false ? "添加箭头" : "移除箭头", style: .default) { [weak self] _ in self?.onCommand?(.edge(id: edge.id, label: alert.textFields?.first?.text ?? edge.label, directed: edge.directed == false, reversed: false)) })
        alert.addAction(UIAlertAction(title: "取消", style: .cancel)); show(alert)
    }
    private func deleteSelection() {
        let ids = selectedIDs
        if board?.groups?.contains(where: { ids.contains($0.id) }) == true {
            let alert = UIAlertController(title: nil, message: nil, preferredStyle: .actionSheet)
            alert.addAction(UIAlertAction(title: "仅移除分组框", style: .default) { [weak self] _ in self?.onCommand?(.delete(ids: ids, includingChildren: false)); self?.selectedIDs = []; self?.updateToolbar() })
            alert.addAction(UIAlertAction(title: "删除分组及内容", style: .destructive) { [weak self] _ in self?.onCommand?(.delete(ids: ids, includingChildren: true)); self?.selectedIDs = []; self?.updateToolbar() })
            alert.addAction(UIAlertAction(title: "取消", style: .cancel)); show(alert)
        } else { onCommand?(.delete(ids: ids, includingChildren: false)); selectedIDs = []; selection = nil; onSelection?(nil); updateToolbar() }
    }
    private func text(_ string: String, _ rect: CGRect, _ font: UIFont, _ color: UIColor) {
        let style = NSMutableParagraphStyle(); style.lineBreakMode = .byWordWrapping; style.lineSpacing = 3
        (string as NSString).draw(with: rect, options: [.usesLineFragmentOrigin, .truncatesLastVisibleLine], attributes: [.font: font, .foregroundColor: color, .paragraphStyle: style], context: nil)
    }
    private func refreshAccessibility() {
        accessibilityElements = board?.visibleCards.compactMap { card -> UIAccessibilityElement? in
            guard !hiddenIDs.contains(card.id) else { return nil }
            let rect = cardRect(card)
            let screen = CGRect(x: rect.minX * scale + translation.x, y: rect.minY * scale + translation.y, width: rect.width * scale, height: rect.height * scale)
            guard screen.intersects(bounds) else { return nil }
            let element = CanvasCardAccessibility(accessibilityContainer: self)
            element.accessibilityIdentifier = "card_\(card.id)"
            element.accessibilityLabel = card.title
            element.accessibilityValue = card.body
            element.accessibilityHint = "打开卡片编辑"
            element.accessibilityTraits = .button
            element.accessibilityFrameInContainerSpace = screen
            element.activate = { [weak self] in self?.onSelection?(card.id); self?.onOpen?(card.id) }
            return element
        }
        for group in board?.groups ?? [] where !hiddenIDs.contains(group.id) {
            guard let rect = groupRect(group) else { continue }
            let screen = CGRect(x: rect.minX * scale + translation.x, y: rect.minY * scale + translation.y, width: rect.width * scale, height: 48 * scale)
            guard screen.intersects(bounds) else { continue }
            let element = CanvasCardAccessibility(accessibilityContainer: self)
            element.accessibilityIdentifier = "group_\(group.id)"
            element.accessibilityLabel = group.title
            element.accessibilityValue = "\(group.cardIDs.count) 张卡片"
            element.accessibilityHint = "展开分组"
            element.accessibilityTraits = .button
            element.accessibilityFrameInContainerSpace = screen
            element.activate = { [weak self] in self?.fit(rect) }
            accessibilityElements?.append(element)
        }
        for edge in board?.edges ?? [] {
            guard let curve = edgeGeometry(edge) else { continue }
            let rect = curve.0.bounds.insetBy(dx: -12, dy: -12)
            let element = CanvasCardAccessibility(accessibilityContainer: self)
            element.accessibilityIdentifier = "edge_\(edge.id)"; element.accessibilityLabel = edge.label.isEmpty ? "连线" : edge.label
            element.accessibilityTraits = .button
            element.accessibilityFrameInContainerSpace = CGRect(x: rect.minX * scale + translation.x, y: rect.minY * scale + translation.y, width: rect.width * scale, height: rect.height * scale)
            element.activate = { [weak self] in self?.selectedIDs = [edge.id]; self?.editEdge(edge) }
            accessibilityElements?.append(element)
        }
        accessibilityElements?.append(multiButton)
        if !toolbar.isHidden { accessibilityElements?.append(contentsOf: toolbar.arrangedSubviews) }
        if !locateButton.isHidden { accessibilityElements?.append(locateButton) }
    }
}

final class CanvasCardAccessibility: UIAccessibilityElement {
    var activate: (() -> Void)?
    override func accessibilityActivate() -> Bool { activate?(); return true }
}

/// Retain touch-down coordinates: UIKit pan translation begins after its recognition threshold.
final class CanvasPanGestureRecognizer: UIPanGestureRecognizer {
    private(set) var initialPoint = CGPoint.zero
    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent) {
        if let touch = touches.first { initialPoint = touch.location(in: view) }
        super.touchesBegan(touches, with: event)
    }
}
