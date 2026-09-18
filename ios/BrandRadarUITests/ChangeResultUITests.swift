import XCTest

final class ChangeResultUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }
    private func wait(_ description: String, _ predicate: @escaping () -> Bool) {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in predicate() }, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [expectation], timeout: 12), .completed, description)
    }
    func testDemoChangeCanBeLocatedReturnedAndUndone() {
        let app = XCUIApplication(); app.launchArguments = ["--uitesting"]; app.launch()
        XCTAssertTrue(app.buttons["fitButton"].waitForExistence(timeout: 10)); app.buttons["fitButton"].tap()
        let card = app.buttons["card_demo_idea"]
        XCTAssertTrue(card.exists)
        let originalBody = card.value as? String ?? ""
        let originalTitle = card.label
        let originalCount = app.staticTexts["cardCountLabel"].label
        card.tap(); app.buttons["chatButton"].tap()
        XCTAssertTrue(app.buttons["demoRefineButton"].waitForExistence(timeout: 5)); app.buttons["demoRefineButton"].tap()
        XCTAssertTrue(app.buttons["chatViewChangesButton"].waitForExistence(timeout: 12))
        XCTAssertTrue(app.buttons["closeChatButton"].exists, "Reply keeps conversation available")
        app.buttons["closeChatButton"].tap()
        wait("Applied result is visible on the canvas") { app.buttons["viewChangesButton"].isHittable && card.exists && (card.value as? String ?? "") != originalBody }
        XCTAssertEqual(app.staticTexts["cardCountLabel"].label, originalCount, "Refinement should not invent new cards")
        XCTAssertTrue(app.staticTexts["changeSummary"].label.contains("修改"))
        let beforeJump = card.frame
        app.buttons["viewChangesButton"].tap()
        XCTAssertTrue(app.buttons["returnCameraButton"].waitForExistence(timeout: 5))
        app.buttons["returnCameraButton"].tap()
        wait("Returning restores the previous camera") {
            abs(card.frame.minX - beforeJump.minX) < 2 && abs(card.frame.minY - beforeJump.minY) < 2 && abs(card.frame.width - beforeJump.width) < 2
        }
        XCTAssertFalse(app.buttons["returnCameraButton"].exists)
        XCTAssertTrue(app.buttons["undoRoundButton"].isEnabled)
        app.buttons["undoRoundButton"].tap()
        wait("Undo restores this round's content") { card.label == originalTitle && (card.value as? String ?? "") == originalBody }
        XCTAssertEqual(app.staticTexts["cardCountLabel"].label, originalCount)
        let shot = XCTAttachment(screenshot: app.screenshot()); shot.name = "B06 round undo restores original canvas"; shot.lifetime = .keepAlways; add(shot)
    }
}
