import XCTest

final class BrandRadarUITests: XCTestCase {
    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    private func launchApp() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments += ["--uitesting"]
        app.launch()
        return app
    }

    func testCanvasAndPrimaryControlsAreAvailable() {
        let app = launchApp()
        XCTAssertTrue(app.descendants(matching: .any)["canvas"].waitForExistence(timeout: 10))
        for identifier in ["templatesButton", "chatButton", "settingsButton", "fitButton", "addNoteButton"] {
            XCTAssertTrue(app.buttons[identifier].exists, "Missing primary control: \(identifier)")
        }
        XCTAssertFalse(app.buttons["modeButton"].exists)
        XCTAssertEqual(app.buttons["chatButton"].label, "输入想法")
    }

    func testChatComposerAcceptsABrief() {
        let app = launchApp()
        let chat = app.buttons["chatButton"]
        XCTAssertTrue(chat.waitForExistence(timeout: 10))
        chat.tap()
        let composer = app.descendants(matching: .any)["composerInput"].firstMatch
        XCTAssertTrue(composer.waitForExistence(timeout: 5))
        composer.tap()
        composer.typeText("Plan a coffee campaign")
        XCTAssertTrue(app.buttons["sendButton"].exists)
        // Deliberately do not submit: this smoke test needs no Mac bridge or model credentials.
    }

    func testTemplateEditingAndPersistence() {
        let app = launchApp()
        XCTAssertTrue(app.buttons["templatesButton"].waitForExistence(timeout: 10))
        app.buttons["templatesButton"].tap()
        app.buttons["template_空白画布"].tap()
        app.buttons["addNoteButton"].tap()
        app.buttons["editCardButton"].tap()
        let title = app.textFields["cardTitleInput"].exists ? app.textFields["cardTitleInput"] : app.textViews["cardTitleInput"]
        XCTAssertTrue(title.waitForExistence(timeout: 5))
        title.tap()
        title.typeText("Weekend Canvas")
        let savedTitle = title.value as? String ?? ""
        XCTAssertTrue(savedTitle.contains("Weekend Canvas"))
        app.buttons["saveCardButton"].tap()
        app.terminate()
        app.launchArguments = ["--uitesting-restore"]
        app.launch()
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_' AND label == %@", savedTitle)).firstMatch.waitForExistence(timeout: 10))
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = "Edited card restored after relaunch"
        screenshot.lifetime = .keepAlways
        add(screenshot)
    }

    func testCanvasPanZoomAndSelection() {
        let app = launchApp()
        XCTAssertTrue(app.buttons["fitButton"].waitForExistence(timeout: 10))
        app.buttons["fitButton"].tap()
        let zoom = app.staticTexts["zoomLabel"].label
        app.pinch(withScale: 1.5, velocity: 1)
        XCTAssertNotEqual(app.staticTexts["zoomLabel"].label, zoom)
        app.buttons["fitButton"].tap()
        let card = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_'")).firstMatch
        XCTAssertTrue(card.exists)
        let origin = card.frame.origin
        let start = card.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
        start.press(forDuration: 0.05, thenDragTo: start.withOffset(CGVector(dx: 35, dy: 40)))
        XCTAssertGreaterThan(card.frame.origin.x, origin.x + 10)
        XCTAssertTrue(app.buttons["editCardButton"].exists)
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = "Native canvas after pinch and card drag"
        screenshot.lifetime = .keepAlways
        add(screenshot)
    }

    func testSlidingAwayBeforeHoldStartsCancelsWithoutOpeningChat() {
        let app = launchApp()
        let chat = app.buttons["chatButton"]
        XCTAssertTrue(chat.waitForExistence(timeout: 10))
        let start = chat.coordinate(withNormalizedOffset: CGVector(dx: 0.65, dy: 0.5))
        // Leave the target before its 0.3-second hold threshold: no permission or microphone is needed.
        start.press(forDuration: 0.05, thenDragTo: start.withOffset(CGVector(dx: 0, dy: -150)),
                    withVelocity: .fast, thenHoldForDuration: 0)
        let unexpectedActivation = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            app.staticTexts["voiceState"].exists ||
            app.descendants(matching: .any)["composerInput"].exists ||
            app.alerts.firstMatch.exists ||
            XCUIApplication(bundleIdentifier: "com.apple.springboard").alerts.firstMatch.exists
        }, object: nil)
        unexpectedActivation.isInverted = true
        XCTAssertEqual(XCTWaiter.wait(for: [unexpectedActivation], timeout: 1), .completed)
        XCTAssertTrue(chat.exists)
        chat.tap()
        XCTAssertTrue(app.descendants(matching: .any)["composerInput"].waitForExistence(timeout: 5))
    }
}
