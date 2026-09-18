import SwiftUI
import UIKit

/// Keep a dirty sheet open until its draft has an explicit disposition.
struct EditorDismissGuard: UIViewControllerRepresentable {
    var isDirty: Bool
    var onAttempt: () -> Void

    func makeUIViewController(context: Context) -> Controller { Controller() }
    func updateUIViewController(_ controller: Controller, context: Context) {
        controller.isDirty = isDirty
        controller.onAttempt = onAttempt
        controller.attach()
        DispatchQueue.main.async { controller.attach() }
    }

    final class Controller: UIViewController, UIAdaptivePresentationControllerDelegate {
        var isDirty = false
        var onAttempt: (() -> Void)?
        override func didMove(toParent parent: UIViewController?) { super.didMove(toParent: parent); attach() }
        override func viewDidAppear(_ animated: Bool) { super.viewDidAppear(animated); attach() }
        override func viewDidLayoutSubviews() { super.viewDidLayoutSubviews(); attach() }
        func attach() {
            // Child controllers inherit presentingViewController; their own presentationController
            // can be an unused object. Only the sheet's outer hosting controller owns dismissal.
            var host: UIViewController = self
            while let parent = host.parent { host = parent }
            guard host.presentingViewController != nil else { return }
            host.presentationController?.delegate = self
            host.isModalInPresentation = isDirty
        }
        func presentationControllerShouldDismiss(_ presentationController: UIPresentationController) -> Bool { !isDirty }
        func presentationControllerDidAttemptToDismiss(_ presentationController: UIPresentationController) { onAttempt?() }
    }
}
