import XCTest

final class ArchiveRestoreUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }
    private func launch() -> XCUIApplication {
        let app = XCUIApplication(); app.launchArguments = ["--uitesting"]; app.launch()
        XCTAssertTrue(app.buttons["fitButton"].waitForExistence(timeout: 10)); app.buttons["fitButton"].tap(); return app
    }
    private func edges(_ app: XCUIApplication) -> Int { app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'edge_'")).count }
    private func archiveIdea(_ app: XCUIApplication) -> String {
        let card = app.buttons["card_demo_idea"], title = card.label
        card.tap(); app.buttons["editCardButton"].tap()
        if !app.buttons["放下"].isHittable { app.swipeUp() }; app.buttons["放下"].tap()
        return title
    }
    private func restore(_ title: String, app: XCUIApplication, expectsMissingRelations: Bool = false) {
        app.buttons["boardsButton"].tap()
        let row = app.buttons[title]; if !row.isHittable { app.swipeUp() }
        XCTAssertTrue(row.waitForExistence(timeout: 5)); row.tap()
        if !app.buttons["恢复"].isHittable { app.swipeUp() }; app.buttons["恢复"].tap()
        if expectsMissingRelations {
            XCTAssertTrue(app.alerts["已恢复可用内容"].waitForExistence(timeout: 5))
            capture("B02 missing relationships explanation", app: app)
        }
        if app.alerts.firstMatch.waitForExistence(timeout: 1) {
            let ok = app.alerts.firstMatch.buttons["知道了"]
            if ok.exists { ok.tap() } else { app.alerts.firstMatch.buttons.firstMatch.tap() }
        }
        app.buttons["完成"].tap(); app.buttons["fitButton"].tap()
        if app.alerts.firstMatch.waitForExistence(timeout: 1) { app.alerts.firstMatch.buttons.firstMatch.tap() }
    }
    private func capture(_ name: String, app: XCUIApplication) { let shot = XCTAttachment(screenshot: app.screenshot()); shot.name = name; shot.lifetime = .keepAlways; add(shot) }
    func testArchiveRestoreRetainsEdgesAndGroup() {
        let app = launch(), before = edges(app), title = archiveIdea(app)
        restore(title, app: app)
        XCTAssertTrue(app.buttons["card_demo_idea"].exists)
        XCTAssertEqual(edges(app), before)
        XCTAssertEqual(app.buttons["group_demo_creation"].value as? String, "2 张卡片")
        capture("B02 restored relationships and membership", app: app)
    }
    func testArchiveRestoreAfterRelaunchRetainsEdgesAndGroup() {
        let app = launch(), before = edges(app), title = archiveIdea(app)
        app.terminate(); app.launchArguments = ["--uitesting-restore"]; app.launch()
        XCTAssertTrue(app.buttons["boardsButton"].waitForExistence(timeout: 10)); restore(title, app: app)
        XCTAssertEqual(edges(app), before)
        XCTAssertEqual(app.buttons["group_demo_creation"].value as? String, "2 张卡片")
        capture("B02 restoration survives relaunch", app: app)
    }
    func testRestoreSkipsDeletedEndpointAndParent() {
        let app = launch(), title = archiveIdea(app)
        app.buttons["card_demo_brief"].tap(); app.buttons["canvas_删除"].tap()
        let parent = app.buttons["group_demo_creation"]
        parent.coordinate(withNormalizedOffset: CGVector(dx: 0.35, dy: 0.5)).tap()
        app.buttons["canvas_删除"].tap(); app.buttons["仅移除分组框"].tap()
        restore(title, app: app, expectsMissingRelations: true)
        XCTAssertTrue(app.buttons["card_demo_idea"].exists)
        XCTAssertFalse(app.buttons["card_demo_brief"].exists)
        XCTAssertFalse(parent.exists)
        XCTAssertEqual(edges(app), 2, "Only surviving question→idea and idea→action may be restored")
        capture("B02 restore skips deleted endpoint and parent", app: app)
    }
}
