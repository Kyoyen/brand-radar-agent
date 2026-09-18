import XCTest

/// Explicit real-device acceptance run after authorized personal provisioning.
/// Creates a separate board and never changes the user's existing boards.
final class LiveDeepSeekUITests: XCTestCase {
    func testPhoneGeneratesAndRevisesWithDeepSeek() throws {
        #if targetEnvironment(simulator)
        throw XCTSkip("Real-phone check; run explicitly after personal Keychain provisioning.")
        #else
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.buttons["settingsButton"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.buttons["modeButton"].exists)
        app.buttons["templatesButton"].tap()
        app.buttons["template_空白画布"].tap()
        send("为一家独立咖啡店做周末活动企划，主题是让咖啡带人走出家门。创建恰好六张卡片：一张主题、两个不同的拍摄想法、每个想法各一张分镜、一张共同的准备清单。用两个分组分别包含想法和它的分镜，六条连线呈现主题分成两路、各自展开、再汇入准备清单。标题直接写内容，正文简短，不需要搜索。", in: app)
        let count = app.staticTexts["cardCountLabel"]
        let generated = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in count.exists && count.label == "6 张卡片" }, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [generated], timeout: 120), .completed)
        XCTAssertTrue(app.buttons["addNoteButton"].isEnabled)
        app.buttons["fitButton"].tap()
        let groups = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'group_'"))
        XCTAssertEqual(groups.count, 2)
        let groupIDs = groups.allElementsBoundByIndex.map(\.identifier)
        let overview = XCTAttachment(screenshot: app.screenshot()); overview.name = "Grouped branching canvas"; overview.lifetime = .keepAlways; add(overview)
        // Move one containing frame; all members and its connections should follow.
        let group = groups.firstMatch
        let start = group.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
        start.press(forDuration: 0.1, thenDragTo: start.withOffset(CGVector(dx: 12, dy: 18)))
        app.buttons["fitButton"].tap()
        let card = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_'" )).firstMatch
        XCTAssertTrue(card.waitForExistence(timeout: 5))
        let id = card.identifier
        let original = card.value as? String ?? ""
        card.tap()
        send("只修改选中的这张卡：改成面向下雨周末的内容，把正文写成三句话。不要新增卡片，不要修改其他卡片和连线。", in: app)
        let revised = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            app.buttons[id].exists && (app.buttons[id].value as? String ?? "") != original && app.buttons["addNoteButton"].isEnabled
        }, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [revised], timeout: 120), .completed)
        XCTAssertEqual(count.label, "6 张卡片")
        XCTAssertEqual(groups.allElementsBoundByIndex.map(\.identifier), groupIDs)
        let newContent = app.buttons[id].value as? String
        let screenshot = XCTAttachment(screenshot: app.screenshot()); screenshot.name = "DeepSeek live phone canvas"; screenshot.lifetime = .keepAlways; add(screenshot)
        app.buttons["chatButton"].tap()
        XCTAssertTrue(app.buttons["closeChatButton"].waitForExistence(timeout: 5))
        let chat = XCTAttachment(screenshot: app.screenshot()); chat.name = "Clear conversation bubbles"; chat.lifetime = .keepAlways; add(chat)
        app.buttons["closeChatButton"].tap()
        app.terminate(); app.launch()
        XCTAssertTrue(app.buttons[id].waitForExistence(timeout: 15))
        XCTAssertEqual(app.buttons[id].value as? String, newContent)
        #endif
    }

    private func send(_ text: String, in app: XCUIApplication) {
        app.buttons["chatButton"].tap()
        let input = app.descendants(matching: .any).matching(identifier: "composerInput").firstMatch
        XCTAssertTrue(input.waitForExistence(timeout: 10))
        input.tap(); input.typeText(text)
        app.buttons["sendButton"].tap()
        XCTAssertTrue(app.buttons["closeChatButton"].waitForExistence(timeout: 5))
        app.buttons["closeChatButton"].tap()
        let canvasVisible = XCTNSPredicateExpectation(predicate: NSPredicate(format: "hittable == true"), object: app.buttons["fitButton"])
        XCTAssertEqual(XCTWaiter.wait(for: [canvasVisible], timeout: 10), .completed)
    }
}
