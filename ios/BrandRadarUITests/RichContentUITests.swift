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
        let item = app.textFields["事项"].firstMatch
        if !item.isHittable { app.swipeUp() }
        XCTAssertTrue(item.waitForExistence(timeout: 5)); item.tap(); item.typeText("Keep this completed item")
        app.buttons["saveCardButton"].tap(); app.buttons["editCardButton"].tap()
        app.swipeUp()
        XCTAssertTrue(app.textFields.matching(NSPredicate(format: "value == %@", "Keep this completed item")).firstMatch.waitForExistence(timeout: 5))
        if !addContent.isHittable { app.swipeUp() }; addContent.tap(); app.buttons["表格"].tap()
        app.buttons["saveCardButton"].tap()
        app.terminate(); app.launchArguments = ["--uitesting-restore"]; app.launch()
        let card = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_'")).firstMatch
        XCTAssertTrue(card.waitForExistence(timeout: 10)); card.tap(); app.buttons["editCardButton"].tap(); app.swipeUp()
        XCTAssertTrue(app.buttons["编辑表格"].waitForExistence(timeout: 5))
        let attachment = XCTAttachment(screenshot: app.screenshot()); attachment.name = "Mixed content persisted"; attachment.lifetime = .keepAlways; add(attachment)
    }
}
