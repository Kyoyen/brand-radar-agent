import XCTest

final class CanvasZoomUITests: XCTestCase {
    func testOverviewCardsRemainSelectableAndMovable() {
        let app = XCUIApplication()
        app.launchArguments = ["--uitesting"]
        app.launch()
        let canvas = app.descendants(matching: .any)["canvas"]
        XCTAssertTrue(canvas.waitForExistence(timeout: 10))

        let middle = XCTAttachment(screenshot: app.screenshot())
        middle.name = "Brandar middle zoom example"
        middle.lifetime = .keepAlways
        add(middle)

        let initialZoom = app.staticTexts["zoomLabel"].label
        app.pinch(withScale: 1.5, velocity: 1)
        XCTAssertNotEqual(app.staticTexts["zoomLabel"].label, initialZoom)

        app.terminate()
        app.launchArguments = ["--uitesting", "--uitesting-overview"]
        app.launch()
        XCTAssertEqual(app.staticTexts["zoomLabel"].label, "27%")
        let far = XCTAttachment(screenshot: app.screenshot())
        far.name = "Brandar far zoom example"
        far.lifetime = .keepAlways
        add(far)

        let card = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_' ")).firstMatch
        XCTAssertTrue(card.waitForExistence(timeout: 5))
        let original = card.frame.origin
        card.tap()
        let selected = XCTAttachment(screenshot: app.screenshot())
        selected.name = "Brandar selected card at far zoom"
        selected.lifetime = .keepAlways
        add(selected)
        let centre = card.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
        centre.press(forDuration: 0.05, thenDragTo: centre.withOffset(CGVector(dx: 30, dy: 20)))
        XCTAssertGreaterThan(card.frame.origin.x, original.x + 10)
    }
}
