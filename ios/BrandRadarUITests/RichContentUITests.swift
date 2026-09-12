import XCTest

final class RichContentUITests: XCTestCase {
    func testChecklistAndTableSaveAndReopen() {
        continueAfterFailure = false
        let app = XCUIApplication(); app.launchArguments = ["--uitesting"]; app.launch()
        XCTAssertTrue(app.buttons["templatesButton"].waitForExistence(timeout: 10))
        app.buttons["templatesButton"].tap(); app.buttons["template_空白画布"].tap()
        app.buttons["addNoteButton"].tap(); app.buttons["editCardButton"].tap()
        let addContent = app.buttons["addContentBlock"]
        XCTAssertTrue(addContent.waitForExistence(timeout: 5)); addContent.tap()
        app.buttons["清单"].tap()
        let item = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'checklistText_'")).firstMatch
        if !item.isHittable { app.swipeUp() }
        XCTAssertTrue(item.waitForExistence(timeout: 5)); item.tap()
        let input = app.textViews["contentValueInput"]
        XCTAssertTrue(input.waitForExistence(timeout: 5)); input.tap(); input.typeText("带上相机，记录沿途的光")
        app.buttons["finishContentValue"].tap()
        let toggle = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'checklistToggle_'")).firstMatch
        XCTAssertGreaterThanOrEqual(toggle.frame.height, 44); toggle.tap()
        app.buttons["saveCardButton"].tap(); app.buttons["editCardButton"].tap()
        app.swipeUp()
        XCTAssertTrue(app.buttons.matching(NSPredicate(format: "label == %@", "带上相机，记录沿途的光")).firstMatch.waitForExistence(timeout: 5))
        if !addContent.isHittable { app.swipeUp() }; addContent.tap(); app.buttons["表格"].tap()
        let cell = app.buttons["tableCell_0_0"]
        if !cell.isHittable { app.swipeUp() }
        XCTAssertTrue(cell.waitForExistence(timeout: 5)); cell.tap()
        XCTAssertTrue(input.waitForExistence(timeout: 5)); input.tap(); input.typeText("出发时间")
        app.buttons["finishContentValue"].tap()
        for (id, value) in [("tableCell_0_1", "随身物品"), ("tableCell_1_0", "周六上午"), ("tableCell_1_1", "相机与笔记本")] {
            app.buttons[id].tap(); XCTAssertTrue(input.waitForExistence(timeout: 5))
            input.tap(); input.typeText(value); app.buttons["finishContentValue"].tap()
        }
        app.buttons["saveCardButton"].tap()
        app.terminate(); app.launchArguments = ["--uitesting-restore"]; app.launch()
        let card = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_'")).firstMatch
        XCTAssertTrue(card.waitForExistence(timeout: 10)); card.tap(); app.buttons["editCardButton"].tap(); app.swipeUp()
        XCTAssertTrue(app.buttons["编辑表格"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["tableCell_0_0"].label.contains("出发时间"))
        XCTAssertEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'checklistToggle_'")).firstMatch.label, "标为未完成")
        let attachment = XCTAttachment(screenshot: app.screenshot()); attachment.name = "Mixed content persisted"; attachment.lifetime = .keepAlways; add(attachment)
    }
}
