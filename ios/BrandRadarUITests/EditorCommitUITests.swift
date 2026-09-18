import XCTest

final class EditorCommitUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }
    private func blankEditor() -> XCUIApplication {
        let app = XCUIApplication(); app.launchArguments = ["--uitesting"]; app.launch()
        XCTAssertTrue(app.buttons["templatesButton"].waitForExistence(timeout: 10))
        app.buttons["templatesButton"].tap(); app.buttons["template_空白画布"].tap()
        app.buttons["addNoteButton"].tap(); app.buttons["editCardButton"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["cardTitleInput"].firstMatch.waitForExistence(timeout: 5))
        return app
    }
    private func appendTitle(_ text: String, app: XCUIApplication) -> String {
        let field = app.descendants(matching: .any)["cardTitleInput"].firstMatch
        field.tap(); field.typeText(text)
        return field.value as? String ?? ""
    }
    private func capture(_ name: String, app: XCUIApplication) {
        let attachment = XCTAttachment(screenshot: app.screenshot()); attachment.name = name; attachment.lifetime = .keepAlways; add(attachment)
    }
    private func cards(_ app: XCUIApplication) -> XCUIElementQuery {
        app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_'"))
    }
    private func cancelEditor(_ app: XCUIApplication) {
        let button = app.buttons["cancelCardButton"]
        if button.exists { button.tap() } else { app.navigationBars.buttons["取消"].tap() }
        if app.buttons["discardEditorChangesButton"].firstMatch.waitForExistence(timeout: 1) { app.buttons["discardEditorChangesButton"].firstMatch.tap() }
    }
    private func swipeEditorDown(_ app: XCUIApplication) {
        let bar = app.navigationBars.firstMatch
        let from = bar.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5))
        from.press(forDuration: 0.1, thenDragTo: from.withOffset(CGVector(dx: 0, dy: 480)), withVelocity: .slow, thenHoldForDuration: 0)
    }
    func testCancelLeavesOriginalAndCreatesNoUndoEntry() {
        let app = blankEditor()
        _ = appendTitle(" Uncommitted", app: app)
        let body = app.textViews["cardBodyInput"]; body.tap(); body.typeText("Unsaved paragraph")
        cancelEditor(app)
        XCTAssertTrue(cards(app).matching(NSPredicate(format: "label == %@", "新便签")).firstMatch.waitForExistence(timeout: 5))
        app.buttons["editCardButton"].tap()
        XCTAssertEqual(app.descendants(matching: .any)["cardTitleInput"].firstMatch.value as? String, "新便签")
        XCTAssertFalse((app.textViews["cardBodyInput"].value as? String ?? "").contains("Unsaved paragraph"))
        cancelEditor(app)
        app.buttons["画布操作"].tap(); app.buttons["撤销"].tap()
        XCTAssertEqual(cards(app).count, 0, "Cancel must not add history after the original add-note operation")
    }
    func testSavePersistsDraftAfterRelaunch() {
        let app = blankEditor(), title = appendTitle(" Saved", app: app)
        app.textViews["cardBodyInput"].tap(); app.textViews["cardBodyInput"].typeText("Saved paragraph")
        app.buttons["saveCardButton"].tap()
        app.terminate(); app.launchArguments = ["--uitesting-restore"]; app.launch()
        let card = cards(app).matching(NSPredicate(format: "label == %@", title)).firstMatch
        XCTAssertTrue(card.waitForExistence(timeout: 10)); card.tap(); app.buttons["editCardButton"].tap()
        XCTAssertTrue((app.textViews["cardBodyInput"].value as? String ?? "").contains("Saved paragraph"))
        capture("B01 saved draft restored", app: app)
    }
    func testSaveAndSplitClosesEditorAndOneUndoRestoresOriginal() {
        let app = blankEditor()
        _ = appendTitle(" Split commit", app: app)
        app.textViews["cardBodyInput"].tap(); app.textViews["cardBodyInput"].typeText("Independent content")
        app.buttons["内容操作"].firstMatch.tap(); app.buttons["保存并转为节点"].tap()
        let confirm = app.buttons["confirmSaveAndSplitButton"].firstMatch
        XCTAssertTrue(confirm.waitForExistence(timeout: 5), "Dirty split must explicitly explain and confirm saving")
        capture("B01 explicit save and split confirmation", app: app)
        confirm.tap()
        let closed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: app.buttons["saveCardButton"])
        XCTAssertEqual(XCTWaiter.wait(for: [closed], timeout: 5), .completed)
        XCTAssertEqual(cards(app).count, 2)
        capture("B01 committed split closes editor", app: app)
        XCTAssertTrue(app.buttons["undoSplitButton"].waitForExistence(timeout: 3))
        app.buttons["undoSplitButton"].tap()
        XCTAssertEqual(cards(app).count, 1)
        XCTAssertEqual(cards(app).firstMatch.label, "新便签", "One undo must restore draft edits and split together")
        capture("B01 single undo restores original", app: app)
    }
    func testDirtySwipeOffersContinueDiscardAndSave() {
        let app = blankEditor()
        let title = appendTitle(" Swipe draft", app: app)
        swipeEditorDown(app)
        for id in ["saveEditorChangesButton", "discardEditorChangesButton", "continueEditingButton"] {
            XCTAssertTrue(app.buttons[id].waitForExistence(timeout: 5), "Missing dirty dismissal action: \(id)")
        }
        capture("B01 dirty dismissal offers three choices", app: app)
        app.buttons["continueEditingButton"].firstMatch.tap()
        XCTAssertEqual(app.descendants(matching: .any)["cardTitleInput"].firstMatch.value as? String, title)
        swipeEditorDown(app); app.buttons["discardEditorChangesButton"].firstMatch.tap()
        XCTAssertEqual(cards(app).firstMatch.label, "新便签")
        app.buttons["editCardButton"].tap(); let saved = appendTitle(" Swipe saved", app: app)
        swipeEditorDown(app); app.buttons["saveEditorChangesButton"].firstMatch.tap()
        XCTAssertEqual(cards(app).firstMatch.label, saved)
    }
    func testCleanSwipeClosesWithoutPrompt() {
        let app = blankEditor(); swipeEditorDown(app)
        XCTAssertTrue(app.buttons["editCardButton"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["discardEditorChangesButton"].firstMatch.exists)
    }
}
