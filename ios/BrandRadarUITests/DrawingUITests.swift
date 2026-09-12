import XCTest

final class DrawingUITests: XCTestCase {
    private func assertStrokes(_ count: Int, on surface: XCUIElement, file: StaticString = #filePath, line: UInt = #line) {
        let expected = XCTNSPredicateExpectation(predicate: NSPredicate(format: "value BEGINSWITH %@", "\(count) 条笔迹"), object: surface)
        XCTAssertEqual(XCTWaiter.wait(for: [expected], timeout: 5), .completed, "Unexpected drawing value: \(surface.value ?? "nil")", file: file, line: line)
    }
    private func drawLine(on surface: XCUIElement, y: CGFloat) {
        let start = surface.coordinate(withNormalizedOffset: CGVector(dx: 0.18, dy: y))
        let end = surface.coordinate(withNormalizedOffset: CGVector(dx: 0.68, dy: y + 0.12))
        start.press(forDuration: 0.05, thenDragTo: end, withVelocity: .slow, thenHoldForDuration: 0.1)
    }
    func testDrawingPersistsAndTopToolbarUndoRedoWorks() {
        continueAfterFailure = false
        let app = XCUIApplication(); app.launchArguments = ["--uitesting"]; app.launch()
        XCTAssertTrue(app.buttons["templatesButton"].waitForExistence(timeout: 10))
        app.buttons["templatesButton"].tap(); app.buttons["template_空白画布"].tap()
        app.buttons["addNoteButton"].tap(); app.buttons["editCardButton"].tap()
        let addContent = app.buttons["addContentBlock"]
        XCTAssertTrue(addContent.waitForExistence(timeout: 5)); addContent.tap(); app.buttons["手绘"].tap()
        let surface = app.descendants(matching: .any)["drawingSurface"].firstMatch
        XCTAssertTrue(surface.waitForExistence(timeout: 5))
        assertStrokes(0, on: surface)
        let undo = app.buttons["drawingUndoButton"], redo = app.buttons["drawingRedoButton"]
        XCTAssertTrue(undo.isHittable && redo.isHittable)
        XCTAssertLessThan(undo.frame.maxY, surface.frame.minY + 50)
        drawLine(on: surface, y: 0.22); assertStrokes(1, on: surface)
        let value = surface.value as? String ?? ""
        let width = value.components(separatedBy: "宽 ").last?.components(separatedBy: "，").first.flatMap(Int.init) ?? 0
        XCTAssertGreaterThan(width, 80, "Slow touch must leave a line, not only a starting dot")
        undo.tap(); assertStrokes(0, on: surface)
        redo.tap(); assertStrokes(1, on: surface)
        let toolbar = XCTAttachment(screenshot: app.screenshot()); toolbar.name = "Drawing toolbar above PencilKit tools"; toolbar.lifetime = .keepAlways; add(toolbar)
        app.buttons["saveDrawingButton"].tap(); app.buttons["saveCardButton"].tap()
        app.terminate(); app.launchArguments = ["--uitesting-restore"]; app.launch()
        let card = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_'")).firstMatch
        XCTAssertTrue(card.waitForExistence(timeout: 10)); card.tap(); app.buttons["editCardButton"].tap()
        let continueDrawing = app.buttons["继续画"]
        if !continueDrawing.isHittable { app.swipeUp() }
        XCTAssertTrue(continueDrawing.waitForExistence(timeout: 5)); continueDrawing.tap()
        XCTAssertTrue(surface.waitForExistence(timeout: 5)); assertStrokes(1, on: surface)
        drawLine(on: surface, y: 0.4); assertStrokes(2, on: surface)
        undo.tap(); assertStrokes(1, on: surface)
        redo.tap(); assertStrokes(2, on: surface)
        app.buttons["saveDrawingButton"].tap(); app.buttons["saveCardButton"].tap()
    }
}
