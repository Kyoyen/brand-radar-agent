import XCTest

final class ChatLibraryUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }
    private func launch(_ extra: String? = nil) -> XCUIApplication {
        let app = XCUIApplication(); app.launchArguments = ["--uitesting"] + (extra.map { [$0] } ?? []); app.launch()
        XCTAssertTrue(app.buttons["chatButton"].waitForExistence(timeout: 10)); return app
    }
    private func input(_ app: XCUIApplication) -> XCUIElement { app.descendants(matching: .any)["composerInput"].firstMatch }
    private func capture(_ name: String, _ app: XCUIApplication) { let shot = XCTAttachment(screenshot: app.screenshot()); shot.name = name; shot.lifetime = .keepAlways; add(shot) }
    func testContinuousLocalConversationKeepsPanelAndTarget() {
        let app = launch(); app.buttons["fitButton"].tap()
        let card = app.buttons["card_demo_idea"]; card.tap(); app.buttons["chatButton"].tap()
        XCTAssertTrue(app.staticTexts["chatTargetLabel"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["chatTargetLabel"].label.contains(card.label))
        for _ in 0..<3 {
            let composer = input(app); composer.tap(); composer.typeText("Rewrite this idea")
            app.buttons["sendButton"].tap()
            XCTAssertTrue(app.buttons["closeChatButton"].exists, "Sending keeps the conversation open")
            let done = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: app.buttons["stopChatButton"])
            XCTAssertEqual(XCTWaiter.wait(for: [done], timeout: 15), .completed)
            XCTAssertTrue(input(app).exists)
            let latestReply = app.staticTexts.matching(NSPredicate(format: "label == %@", "这张已改好，旧稿也留着。")).allElementsBoundByIndex.last!
            let visible = XCTNSPredicateExpectation(predicate: NSPredicate(format: "hittable == true"), object: latestReply)
            XCTAssertEqual(XCTWaiter.wait(for: [visible], timeout: 5), .completed, "Latest reply is readable after layout settles: \(app.scrollViews["chatHistory"].value ?? "nil")")
        }
        capture("B03 three local edits in one panel", app)
    }
    func testGroupTargetNamesItsContents() {
        let app = launch(); app.buttons["fitButton"].tap()
        let group = app.buttons["group_demo_creation"]
        group.coordinate(withNormalizedOffset: CGVector(dx: 0.35, dy: 0.5)).tap()
        app.buttons["chatButton"].tap()
        XCTAssertTrue(app.staticTexts["chatTargetLabel"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["chatTargetLabel"].label.contains("把想法拍出来"))
        XCTAssertTrue(app.staticTexts["chatTargetLabel"].label.contains("2"))
        capture("B03 group target and scope", app)
    }
    func testUnsentDraftSurvivesPanelCloseAndRelaunch() {
        let app = launch(); app.buttons["chatButton"].tap()
        input(app).tap(); input(app).typeText("An unfinished thought")
        app.buttons["closeChatButton"].tap(); app.buttons["chatButton"].tap()
        XCTAssertEqual(input(app).value as? String, "An unfinished thought")
        app.terminate(); app.launchArguments = ["--uitesting-restore"]; app.launch()
        XCTAssertTrue(app.buttons["chatButton"].waitForExistence(timeout: 10)); app.buttons["chatButton"].tap()
        XCTAssertEqual(input(app).value as? String, "An unfinished thought")
        capture("B04 editable draft restored", app)
    }
    func testReadingHistoryIsNotMovedByNewReply() {
        let app = launch("--uitesting-chat-history"); app.buttons["chatButton"].tap()
        let history = app.scrollViews["chatHistory"]
        XCTAssertTrue(history.waitForExistence(timeout: 5))
        history.swipeDown(); history.swipeDown()
        XCTAssertTrue(app.buttons["newReplyButton"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.staticTexts["新回复：继续补充了刚才的安排。"].isHittable)
        capture("B03 new reply waits while reading history", app)
        app.buttons["newReplyButton"].tap()
        XCTAssertTrue(app.staticTexts["新回复：继续补充了刚才的安排。"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["新回复：继续补充了刚才的安排。"].isHittable)
    }
    func testLibrarySearchTitleBodyEmptyAndClear() {
        let app = launch("--uitesting-library"); app.buttons["boardsButton"].tap()
        let search = app.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 5)); search.tap(); search.typeText("湖畔方案")
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'board_' AND label CONTAINS %@", "湖畔方案")).firstMatch.waitForExistence(timeout: 5))
        search.buttons.firstMatch.tap(); search.typeText("蓝色风筝")
        let result = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'board_'")).firstMatch
        XCTAssertTrue(result.waitForExistence(timeout: 5)); capture("B08 body search finds existing canvas", app)
        search.buttons.firstMatch.tap(); search.typeText("NoSuchCanvas98765")
        XCTAssertTrue(app.descendants(matching: .any)["boardSearchEmpty"].firstMatch.waitForExistence(timeout: 5))
        search.buttons.firstMatch.tap(); search.typeText("湖畔方案")
        app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'board_'")).firstMatch.tap()
        XCTAssertTrue(app.staticTexts["boardTitle"].label.contains("湖畔方案"))
        app.buttons["boardsButton"].tap(); XCTAssertTrue(app.searchFields.firstMatch.waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'archived_'")).firstMatch.exists)
    }
}
