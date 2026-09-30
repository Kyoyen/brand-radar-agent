import XCTest

/// Explicit opt-in. Uses a dedicated canvas file and real saved API credentials.
/// The visual assets and segmented transcript are synthetic; microphone and ASR are not tested.
final class LiveAcceptanceUITests: XCTestCase {
    private func requireOptIn() throws {
        guard ProcessInfo.processInfo.environment["BRANDAR_LIVE_ACCEPTANCE"] == "1" else {
            throw XCTSkip("Set BRANDAR_LIVE_ACCEPTANCE=1 and provision the dedicated simulator before running live API acceptance.")
        }
    }

    private func cardIDs(in app: XCUIApplication) -> [String] {
        app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_'"))
            .allElementsBoundByIndex.map(\.identifier).sorted()
    }

    private func waitForCards(_ minimum: Int, in app: XCUIApplication, timeout: TimeInterval = 180) -> Bool {
        let label = app.staticTexts["cardCountLabel"]
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            let count = Int(label.label.split(separator: " ").first ?? "") ?? 0
            return count >= minimum || app.alerts.firstMatch.exists
        }, object: nil)
        return XCTWaiter.wait(for: [expectation], timeout: timeout) == .completed &&
            (Int(label.label.split(separator: " ").first ?? "") ?? 0) >= minimum
    }

    func testSyntheticImageAndDrawingReachRealModelAndPersist() throws {
        try requireOptIn()
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["--live-acceptance", "--live-acceptance-material"]
        app.launch()
        XCTAssertTrue(app.buttons["settingsButton"].waitForExistence(timeout: 15))
        XCTAssertTrue(waitForCards(1, in: app, timeout: 10))
        let original = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_'" )).firstMatch
        XCTAssertTrue(original.waitForExistence(timeout: 10))
        let originalID = original.identifier
        original.tap()
        app.buttons["chatButton"].tap()
        let composer = app.descendants(matching: .any)["composerInput"].firstMatch
        XCTAssertTrue(composer.waitForExistence(timeout: 10))
        composer.tap()
        composer.typeText("请分别读取选中素材里的图片和手绘：图片有两个英文标签，手绘有两个数字。按每份素材看到的方向分别建立可编辑节点和有向关系；保留原素材卡，无法辨认时说明问题，不猜答案。")
        app.buttons["sendButton"].tap()
        app.buttons["closeChatButton"].tap()
        let generatedEnough = waitForCards(5, in: app)
        let alertText = app.alerts.firstMatch.staticTexts.allElementsBoundByIndex.map(\.label).joined(separator: " | ")
        if !generatedEnough {
            let failureScreenshot = XCTAttachment(screenshot: app.screenshot())
            failureScreenshot.name = "Real visual request failure"
            failureScreenshot.lifetime = .keepAlways
            add(failureScreenshot)
        }
        XCTAssertTrue(generatedEnough, "Two visual sources should yield four editable label nodes. App alert: \(alertText)")
        let settled = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in
            app.staticTexts["cardCountLabel"].value as? String == "已完成"
        }, object: nil)
        XCTAssertEqual(XCTWaiter.wait(for: [settled], timeout: 180), .completed, "Capture IDs only after the real request ends.")
        app.buttons["fitButton"].tap()
        let after = cardIDs(in: app)
        XCTAssertTrue(after.contains(originalID))
        XCTAssertGreaterThanOrEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'edge_'" )).count, 2)
        let screenshot = XCTAttachment(screenshot: app.screenshot()); screenshot.name = "Synthetic visual originals and real model structure"; screenshot.lifetime = .keepAlways; add(screenshot)
        app.terminate()
        app.launchArguments = ["--live-acceptance"]
        app.launch()
        XCTAssertTrue(waitForCards(after.count, in: app, timeout: 10))
        app.buttons["fitButton"].tap()
        XCTAssertTrue(app.buttons[originalID].waitForExistence(timeout: 15))
        XCTAssertEqual(cardIDs(in: app), after, "Restart must preserve every generated card ID.")
    }

    func testSyntheticSegmentsUseProductionVoiceStoreAndReviewSurvivesRestart() throws {
        try requireOptIn()
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchArguments = ["--live-acceptance", "--live-acceptance-material", "--live-acceptance-synthetic-speech"]
        app.launch()
        XCTAssertTrue(app.buttons["keepLiveDrawingButton"].waitForExistence(timeout: 300))
        XCTAssertTrue(waitForCards(3, in: app, timeout: 10))
        let IDs = cardIDs(in: app)
        XCTAssertGreaterThanOrEqual(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'edge_'" )).count, 1)
        app.buttons["reviewFitButton"].tap()
        let screenshot = XCTAttachment(screenshot: app.screenshot()); screenshot.name = "Synthetic transcript real API review"; screenshot.lifetime = .keepAlways; add(screenshot)
        app.terminate()
        app.launchArguments = ["--live-acceptance"]
        app.launch()
        XCTAssertTrue(app.buttons["keepLiveDrawingButton"].waitForExistence(timeout: 15))
        app.buttons["reviewFitButton"].tap()
        XCTAssertEqual(cardIDs(in: app), IDs, "Unconfirmed model changes must survive restart with stable IDs.")
        app.buttons["keepLiveDrawingButton"].tap()
        XCTAssertFalse(app.buttons["keepLiveDrawingButton"].waitForExistence(timeout: 2))
        app.terminate(); app.launch()
        app.buttons["fitButton"].tap()
        XCTAssertEqual(cardIDs(in: app), IDs, "Accepted changes must survive another restart.")
    }
}
