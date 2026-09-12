import XCTest

final class LiveDrawingUITests: XCTestCase {
    func testBriefAndBetaAreSeparateEntrypoints() {
        let app = XCUIApplication(); app.launchArguments = ["--uitesting"]; app.launch()
        XCTAssertTrue(app.buttons["briefModeButton"].waitForExistence(timeout: 10))
        app.buttons["liveDrawingModeButton"].tap()
        XCTAssertTrue(app.buttons["briefModeButton"].isEnabled)
        app.buttons["briefModeButton"].tap()
        XCTAssertFalse(app.staticTexts["liveDrawingReview"].exists)
    }
    func testKeepAndDiscardReviewSurviveRestart() {
        continueAfterFailure = false
        let app = XCUIApplication(); app.launchArguments = ["--uitesting", "--live-review-fixture"]; app.launch()
        XCTAssertTrue(app.buttons["keepLiveDrawingButton"].waitForExistence(timeout: 10))
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
