import XCTest

final class DemoModeUITests: XCTestCase {
    override func setUpWithError() throws { continueAfterFailure = false }

    private func launch(_ restoring: Bool = false) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = [restoring ? "--uitesting-restore" : "--uitesting"]
        app.launch()
        XCTAssertTrue(app.buttons["settingsButton"].waitForExistence(timeout: 10))
        return app
    }

    private func waitFor(_ description: String, timeout: TimeInterval = 10,
                         _ condition: @escaping () -> Bool) {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate { _, _ in condition() }, object: nil)
        let result = XCTWaiter.wait(for: [expectation], timeout: timeout)
        if result != .completed {
            let screenshot = XCTAttachment(screenshot: XCUIApplication().screenshot())
            screenshot.name = description
            screenshot.lifetime = .keepAlways
            add(screenshot)
        }
        XCTAssertEqual(result, .completed, description)
    }

    private func input(_ identifier: String, in app: XCUIApplication) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: identifier).firstMatch
    }

    private func replaceText(_ element: XCUIElement, with text: String) {
        XCTAssertTrue(element.waitForExistence(timeout: 5))
        element.tap()
        let existing = element.value as? String ?? ""
        if !existing.isEmpty && existing != element.placeholderValue {
            element.press(forDuration: 1.1)
            let app = XCUIApplication()
            let selectAll = app.descendants(matching: .any)
                .matching(NSPredicate(format: "label IN {'全选', 'Select All'}")).firstMatch
            guard selectAll.waitForExistence(timeout: 3) else {
                XCTFail("Native Select All menu is unavailable: \(app.debugDescription)")
                return
            }
            selectAll.tap()
        }
        element.typeText(text)
        XCTAssertEqual(element.value as? String, text, "Replacement must not depend on the cursor's initial position")
    }

    private func switchMode(_ mode: String, in app: XCUIApplication) {
        openSettings(in: app)
        let picker = app.buttons["modePicker"]
        XCTAssertTrue(picker.waitForExistence(timeout: 5))
        XCTAssertTrue(picker.isEnabled)
        let target = mode == "实操" ? "我的画布" : "示例画布"
        if picker.value as? String == target { closeSettings(in: app) }
        else { XCTAssertEqual(picker.label, target); picker.tap() }
        waitFor("The settings sheet finishes dismissing") {
            !app.buttons["closeSettingsButton"].exists && app.buttons["settingsButton"].isHittable
        }
    }

    private func openSettings(in app: XCUIApplication) {
        waitFor("The settings entry is ready to tap") { app.buttons["settingsButton"].isHittable }
        app.buttons["settingsButton"].tap()
        XCTAssertTrue(app.buttons["connectionSettingsButton"].waitForExistence(timeout: 5))
    }

    private func closeSettings(in app: XCUIApplication) {
        app.buttons["closeSettingsButton"].tap()
        waitFor("The settings sheet finishes dismissing") {
            !app.buttons["closeSettingsButton"].exists && app.buttons["settingsButton"].isHittable
        }
    }

    private func createNote(_ title: String, in app: XCUIApplication) -> String {
        app.buttons["templatesButton"].tap()
        app.buttons["template_空白画布"].tap()
        app.buttons["addNoteButton"].tap()
        app.buttons["editCardButton"].tap()
        replaceText(input("cardTitleInput", in: app), with: title)
        app.buttons["saveCardButton"].tap()
        app.buttons["fitButton"].tap()
        let card = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_' AND label == %@", title)).firstMatch
        XCTAssertTrue(card.waitForExistence(timeout: 5))
        return card.identifier
    }

    func testOfflineDemoGeneratesRefinesAndRestoresTheSameCard() {
        let app = launch()
        XCTAssertFalse(app.buttons["modeButton"].exists)
        XCTAssertEqual(app.staticTexts["cardCountLabel"].label, "4 张卡片")
        let originalIDs = Set(app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_'"))
            .allElementsBoundByIndex.map(\.identifier))
        app.buttons["chatButton"].tap()
        XCTAssertTrue(app.buttons["demoStartButton"].waitForExistence(timeout: 5))
        app.buttons["demoStartButton"].tap()
        XCTAssertTrue(app.buttons["fitButton"].waitForExistence(timeout: 10))
        app.buttons["fitButton"].tap()
        waitFor("Demo must create new visible cards without credentials") {
            app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_'"))
                .allElementsBoundByIndex.contains { !originalIDs.contains($0.identifier) }
        }
        XCTAssertEqual(app.staticTexts["cardCountLabel"].label, "7 张卡片")
        let generated = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'card_'"))
            .allElementsBoundByIndex.first { !originalIDs.contains($0.identifier) }!
        let cardID = generated.identifier
        let oldBody = generated.value as? String ?? ""
        XCTAssertTrue(app.staticTexts["cardCountLabel"].exists)
        let count = app.staticTexts["cardCountLabel"].label
        generated.tap()
        XCTAssertTrue(app.buttons["editCardButton"].waitForExistence(timeout: 5))
        app.buttons["chatButton"].tap()
        XCTAssertTrue(app.buttons["demoRefineButton"].waitForExistence(timeout: 5))
        app.buttons["demoRefineButton"].tap()
        XCTAssertTrue(app.buttons["fitButton"].waitForExistence(timeout: 10))
        app.buttons["fitButton"].tap()
        waitFor("Refining must update the selected card, keeping its identity") {
            app.buttons[cardID].exists && (app.buttons[cardID].value as? String ?? "") != oldBody
        }
        XCTAssertEqual(app.staticTexts["cardCountLabel"].label, count, "Refining should not duplicate cards")
        app.buttons[cardID].tap()
        app.buttons["editCardButton"].tap()
        replaceText(input("cardTitleInput", in: app), with: "Demo work saved on phone")
        app.buttons["saveCardButton"].tap()
        app.terminate()
        let restored = launch(true)
        XCTAssertTrue(restored.buttons[cardID].waitForExistence(timeout: 10))
        XCTAssertEqual(restored.buttons[cardID].label, "Demo work saved on phone")
    }

    func testModeSwitchAndDemoResetPreserveRealWork() {
        let app = launch()
        let demoID = createNote("Only in demo", in: app)
        switchMode("实操", in: app)
        XCTAssertFalse(app.buttons[demoID].exists)
        let realID = createNote("Real work must stay", in: app)
        switchMode("演示", in: app)
        XCTAssertTrue(app.buttons[demoID].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons[realID].exists)
        openSettings(in: app)
        let reset = app.buttons["resetDemoButton"]
        XCTAssertTrue(reset.waitForExistence(timeout: 5))
        if !reset.isHittable { app.swipeUp() }
        reset.tap()
        XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 3))
        app.alerts.firstMatch.buttons["重置"].tap()
        if app.buttons["closeSettingsButton"].exists { closeSettings(in: app) }
        XCTAssertFalse(app.buttons[demoID].exists)
        switchMode("实操", in: app)
        XCTAssertTrue(app.buttons[realID].waitForExistence(timeout: 5))
        XCTAssertEqual(app.buttons[realID].label, "Real work must stay")
        app.terminate()
        let restored = launch(true)
        XCTAssertTrue(restored.buttons[realID].waitForExistence(timeout: 5))
    }

    func testEmptyAPIKeyCannotSaveAndTheBriefSurvives() {
        let app = launch()
        switchMode("实操", in: app)
        openSettings(in: app)
        app.buttons["connectionSettingsButton"].tap()
        let baseURL = input("apiBaseURLInput", in: app)
        XCTAssertTrue(baseURL.waitForExistence(timeout: 5))
        if !baseURL.isHittable { app.swipeUp() }
        replaceText(baseURL, with: "https://api.example.com/v1")
        replaceText(input("apiModelInput", in: app), with: "demo-model")
        let save = app.buttons["apiSaveButton"]
        XCTAssertTrue(save.exists)
        XCTAssertFalse(save.isEnabled, "An empty key must not be accepted as a valid configuration")
        closeSettings(in: app)
        app.buttons["chatButton"].tap()
        let brief = "Keep this brief even when there is no API key"
        replaceText(input("composerInput", in: app), with: brief)
        app.buttons["sendButton"].tap()
        waitFor("Missing credentials should explain how to configure the connection", timeout: 5) {
            app.staticTexts["chatError"].exists || app.alerts.firstMatch.exists
        }
        if app.alerts.firstMatch.exists { app.alerts.firstMatch.buttons.firstMatch.tap() }
        if !input("composerInput", in: app).exists { app.buttons["chatButton"].tap() }
        let visibleBrief = app.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", brief)).firstMatch
        waitFor("A failed brief remains available to copy or edit") {
            visibleBrief.exists || (self.input("composerInput", in: app).value as? String ?? "").contains(brief)
        }
        app.terminate()
        let restored = launch(true)
        restored.buttons["chatButton"].tap()
        waitFor("The failed brief survives an app restart", timeout: 5) {
            restored.staticTexts.matching(NSPredicate(format: "label CONTAINS %@", brief)).firstMatch.exists ||
            (self.input("composerInput", in: restored).value as? String ?? "").contains(brief)
        }
    }

    func testAPIKeySavesAndCanBeRemovedWithoutNetworking() {
        let app = launch()
        switchMode("实操", in: app)
        openSettings(in: app)
        app.buttons["connectionSettingsButton"].tap()
        replaceText(input("apiBaseURLInput", in: app), with: "https://brandradar-ui-test.invalid/v1")
        replaceText(input("apiModelInput", in: app), with: "ui-test")
        let key = input("apiKeyInput", in: app)
        XCTAssertTrue(key.waitForExistence(timeout: 5))
        key.tap()
        key.typeText("obviously-fake-ui-test-key-not-a-secret")
        let save = app.buttons["apiSaveButton"]
        XCTAssertTrue(save.isEnabled)
        if !save.isHittable { app.swipeUp() }
        save.tap()
        waitFor("Saving a nonsecret test key should confirm local persistence") {
            app.staticTexts["apiFeedback"].label.contains("已保存")
        }
        let visibleKey = key.value as? String ?? ""
        XCTAssertTrue(visibleKey.isEmpty || visibleKey == key.placeholderValue,
                      "The secure input must be cleared after saving")
        closeSettings(in: app)
        app.terminate()
        let restored = launch(true)
        openSettings(in: restored)
        restored.buttons["connectionSettingsButton"].tap()
        let remove = restored.buttons["移除已保存的 Key"]
        XCTAssertTrue(remove.waitForExistence(timeout: 5), "A relaunch must read the saved key from Keychain")
        for _ in 0..<3 where !remove.isHittable { restored.swipeUp() }
        remove.tap()
        XCTAssertTrue(restored.alerts["移除这个 Key？"].waitForExistence(timeout: 3))
        restored.alerts["移除这个 Key？"].buttons["移除"].tap()
        waitFor("Removing the test key must restore the unconfigured state") {
            !restored.buttons["移除已保存的 Key"].exists && !restored.buttons["apiTestButton"].isEnabled
        }
        // No connection test or model request is sent; the reserved .invalid endpoint cannot be a real service.
    }
}
