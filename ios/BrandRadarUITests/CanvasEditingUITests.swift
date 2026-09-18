import XCTest

final class CanvasEditingUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }
    override func tearDownWithError() throws {
        if (testRun?.failureCount ?? 0) > 0 {
            let shot = XCTAttachment(screenshot: XCUIApplication().screenshot())
            shot.name = "Canvas interaction failure"; shot.lifetime = .keepAlways; add(shot)
        }
    }
    private func launch() -> XCUIApplication {
        let app = XCUIApplication(); app.launchArguments = ["--uitesting"]; app.launch()
        XCTAssertTrue(app.buttons["fitButton"].waitForExistence(timeout: 10)); app.buttons["fitButton"].tap()
        return app
    }
    private func wait(_ predicate: @escaping () -> Bool, file: StaticString = #filePath, line: UInt = #line) {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in predicate() }, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [expectation], timeout: 5), .completed, file: file, line: line)
    }
    func testGroupCollapseExpandAndUngroupKeepsCards() {
        let app = launch(), group = app.buttons["group_demo_creation"]
        let idea = app.buttons["card_demo_idea"]
        XCTAssertTrue(group.exists); XCTAssertTrue(idea.exists)
        group.coordinate(withNormalizedOffset: CGVector(dx: 0.96, dy: 0.5)).tap()
        wait { !idea.exists }
        XCTAssertTrue(group.exists)
        group.coordinate(withNormalizedOffset: CGVector(dx: 0.96, dy: 0.5)).tap()
        wait { idea.exists }
        group.coordinate(withNormalizedOffset: CGVector(dx: 0.35, dy: 0.5)).tap()
        XCTAssertTrue(app.buttons["canvas_解散分组"].waitForExistence(timeout: 3))
        app.buttons["canvas_解散分组"].tap()
        wait { !group.exists }
        XCTAssertTrue(idea.exists); XCTAssertTrue(app.buttons["card_demo_action"].exists)
    }
    func testResizeChangesGeometryAndPersists() {
        let app = launch(), card = app.buttons["card_demo_idea"]
        card.tap(); XCTAssertTrue(app.buttons["editCardButton"].waitForExistence(timeout: 3))
        let original = card.frame.size
        let handle = card.coordinate(withNormalizedOffset: CGVector(dx: 1, dy: 1))
        handle.press(forDuration: 0.05, thenDragTo: handle.withOffset(CGVector(dx: 20, dy: 24)))
        wait { card.frame.width > original.width + 10 && card.frame.height > original.height + 10 }
        let resized = card.frame.size
        app.terminate(); app.launchArguments = ["--uitesting-restore"]; app.launch()
        XCTAssertTrue(card.waitForExistence(timeout: 10))
        XCTAssertEqual(card.frame.width, resized.width, accuracy: 2)
        XCTAssertEqual(card.frame.height, resized.height, accuracy: 2)
    }
    func testMultiSelectionCreatesGroupWithoutLosingMembers() {
        let app = launch()
        let originalCount = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'group_'")).count
        app.buttons["canvasMultiSelect"].tap()
        app.buttons["card_demo_brief"].tap(); app.buttons["card_demo_idea"].tap()
        XCTAssertTrue(app.buttons["canvas_分组"].waitForExistence(timeout: 3)); app.buttons["canvas_分组"].tap()
        wait { app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'group_'")).count == originalCount + 1 }
        XCTAssertTrue(app.buttons["card_demo_brief"].exists); XCTAssertTrue(app.buttons["card_demo_idea"].exists)
    }
    func testTapConnectionAllowsBackEdge() {
        let app = launch()
        let edgeCount = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'edge_'")).count
        app.buttons["card_demo_action"].tap()
        app.buttons["canvas_cardMore"].tap(); app.buttons["连接"].tap(); app.buttons["card_demo_brief"].tap()
        wait { app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'edge_'")).count == edgeCount + 1 }
        // The new back edge exercises allowed graph cycles without containment changes.
        let edge = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'edge_' AND label == '关联'")).firstMatch
        XCTAssertTrue(edge.exists)
        let shot = XCTAttachment(screenshot: app.screenshot()); shot.name = "Editable graph with back edge"; shot.lifetime = .keepAlways; add(shot)
    }

    func testVisibleReaderReturnsToUnchangedCanvasAndCanEdit() {
        let app = launch(), card = app.buttons["card_demo_idea"]
        let before = card.frame
        card.tap()
        XCTAssertTrue(app.buttons["canvas_阅读"].waitForExistence(timeout: 3))
        XCTAssertGreaterThanOrEqual(app.buttons["canvas_阅读"].frame.height, 44)
        app.buttons["canvas_阅读"].tap()
        XCTAssertTrue(app.scrollViews["cardReaderContent"].waitForExistence(timeout: 3))
        XCTAssertTrue(app.buttons["readerContinue"].exists)
        XCTAssertTrue(app.buttons["readerEdit"].exists)
        let shot = XCTAttachment(screenshot: app.screenshot()); shot.name = "B05 full card reader"; shot.lifetime = .keepAlways; add(shot)
        app.buttons["closeCardReader"].tap()
        XCTAssertTrue(card.waitForExistence(timeout: 3))
        XCTAssertEqual(card.frame.minX, before.minX, accuracy: 1)
        XCTAssertEqual(card.frame.minY, before.minY, accuracy: 1)
        XCTAssertEqual(card.frame.width, before.width, accuracy: 1)
        app.buttons["canvas_阅读"].tap()
        app.buttons["readerEdit"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["cardTitleInput"].firstMatch.waitForExistence(timeout: 3))
    }
    func testConnectionDroppedOnEmptyOffersNewNode() {
        let app = launch(), card = app.buttons["card_demo_action"]
        card.tap()
        let port = card.coordinate(withNormalizedOffset: CGVector(dx: 1, dy: 0.5))
        let canvas = app.descendants(matching: .any)["canvas"].firstMatch
        let empty = canvas.coordinate(withNormalizedOffset: CGVector(dx: 0.12, dy: 0.72))
        port.press(forDuration: 0.05, thenDragTo: empty)
        XCTAssertTrue(app.buttons["新建节点"].waitForExistence(timeout: 3)); app.buttons["新建节点"].tap()
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_' AND label == '新节点'")).firstMatch.waitForExistence(timeout: 3))
    }
}
