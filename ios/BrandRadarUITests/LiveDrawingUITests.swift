import XCTest

final class LiveDrawingUITests: XCTestCase {
    func testBriefAndBetaAreSeparateEntrypoints() {
        let app = XCUIApplication(); app.launchArguments = ["--uitesting"]; app.launch()
        XCTAssertTrue(app.buttons["briefModeButton"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["chatButton"].label.contains("输入想法"))
        app.buttons["liveDrawingModeButton"].tap()
        XCTAssertTrue(app.buttons["chatButton"].label.contains("边说边画"))
        XCTAssertTrue(app.buttons["briefModeButton"].isEnabled)
        app.buttons["chatButton"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["composerInput"].waitForExistence(timeout: 5))
        app.buttons["closeChatButton"].tap()
        app.buttons["briefModeButton"].tap()
        XCTAssertFalse(app.staticTexts["liveDrawingReview"].exists)
    }
    func testDemoBriefCanContinueInMyCanvas() {
        let app = XCUIApplication(); app.launchArguments = ["--uitesting"]; app.launch()
        app.buttons["chatButton"].tap()
        let composer = app.descendants(matching: .any)["composerInput"].firstMatch
        XCTAssertTrue(composer.waitForExistence(timeout: 5))
        composer.tap(); composer.typeText("My own idea")
        XCTAssertTrue(app.buttons["copyDemoToMyBoardButton"].exists)
        app.buttons["copyDemoToMyBoardButton"].tap()
        XCTAssertFalse(app.buttons["copyDemoToMyBoardButton"].exists)
        XCTAssertTrue((composer.value as? String ?? "").contains("My own idea"))
    }
    func testKeepAndDiscardReviewSurviveRestart() {
        continueAfterFailure = false
        let app = XCUIApplication(); app.launchArguments = ["--uitesting", "--live-review-fixture"]; app.launch()
        XCTAssertTrue(app.buttons["keepLiveDrawingButton"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["liveDrawingReview"].label.contains("画布变化"))
        XCTAssertTrue(app.buttons["reviewFitButton"].exists)
        app.buttons["reviewFitButton"].tap()
        XCTAssertTrue(app.buttons["keepLiveDrawingButton"].exists)
        app.terminate(); app.launchArguments = ["--uitesting-restore"]; app.launch()
        XCTAssertTrue(app.buttons["discardLiveDrawingButton"].waitForExistence(timeout: 10))
        app.buttons["discardLiveDrawingButton"].tap()
        XCTAssertFalse(app.buttons["keepLiveDrawingButton"].exists)
        XCTAssertFalse(app.buttons["card_beta-review-card"].exists)
        app.terminate(); app.launchArguments = ["--uitesting", "--live-review-fixture"]; app.launch()
        XCTAssertTrue(app.buttons["keepLiveDrawingButton"].waitForExistence(timeout: 10))
        app.buttons["keepLiveDrawingButton"].tap()
        XCTAssertFalse(app.buttons["discardLiveDrawingButton"].exists)
        app.terminate(); app.launchArguments = ["--uitesting-restore"]; app.launch()
        XCTAssertFalse(app.buttons["keepLiveDrawingButton"].waitForExistence(timeout: 2))
        app.buttons["fitButton"].tap()
        XCTAssertTrue(app.buttons["card_beta-review-card"].waitForExistence(timeout: 5))
    }
}
