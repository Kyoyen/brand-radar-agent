import XCTest

final class CanvasGroupUITests: XCTestCase {
    func testGroupDragMovesMembersAndPersists() {
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["--uitesting"]
        app.launch()
        XCTAssertTrue(app.buttons["fitButton"].waitForExistence(timeout: 10))
        app.buttons["fitButton"].tap()
        let group = app.buttons["group_demo_creation"]
        XCTAssertTrue(group.waitForExistence(timeout: 5))
        let idea = app.buttons["card_demo_idea"], action = app.buttons["card_demo_action"]
        let unrelated = app.buttons["card_demo_brief"]
        let a = idea.frame.origin, b = action.frame.origin, c = unrelated.frame.origin
        let start = group.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
        start.press(forDuration: 0.05, thenDragTo: start.withOffset(CGVector(dx: 25, dy: -20)))
        XCTAssertGreaterThan(idea.frame.origin.x, a.x + 10)
        XCTAssertEqual(idea.frame.origin.x - a.x, action.frame.origin.x - b.x, accuracy: 2)
        XCTAssertEqual(idea.frame.origin.y - a.y, action.frame.origin.y - b.y, accuracy: 2)
        XCTAssertEqual(unrelated.frame.origin.x, c.x, accuracy: 2)
        XCTAssertEqual(unrelated.frame.origin.y, c.y, accuracy: 2)
        let moved = idea.frame.origin
        app.terminate(); app.launchArguments = ["--uitesting-restore"]; app.launch()
        XCTAssertTrue(idea.waitForExistence(timeout: 10))
        XCTAssertEqual(idea.frame.origin.x, moved.x, accuracy: 2)
        XCTAssertEqual(idea.frame.origin.y, moved.y, accuracy: 2)
        group.tap()
        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = "Groups after persistent drag"; shot.lifetime = .keepAlways; add(shot)
    }
}
