"""Deliver the authorized local DeepSeek connection to this app's Keychain inbox.

The temporary key file is private, never printed, and removed on every exit.
The app consumes and deletes its inbox on the next unlocked launch.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    values = dotenv_values(root / ".env")
    if (values.get("LLM_PROVIDER") or "deepseek").lower() != "deepseek":
        raise SystemExit("The project is not configured for DeepSeek.")
    key = values.get("DEEPSEEK_API_KEY") or ""
    model = values.get("LLM_MODEL") or ""
    if not key or not model:
        raise SystemExit("The project DeepSeek configuration is incomplete.")
    outputs = root / "outputs"
    outputs.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phone-setup-", dir=outputs) as folder:
        source = Path(folder) / "AgentSetup.json"
        payload = {"configuration": {"provider": "DeepSeek", "baseURL": "https://api.deepseek.com/v1", "model": model}, "apiKey": key}
        descriptor = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as file:
            json.dump(payload, file)
        command = ["xcrun", "devicectl", "device", "copy", "to", "--device", args.device,
                   "--source", str(source), "--destination", "Library/Application Support/AgentSetup.json",
                   "--domain-type", "appDataContainer", "--domain-identifier", "com.keyuanshi.brandradar", "--timeout", "45", "--quiet"]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=55)
        if result.returncode:
            raise SystemExit("Phone configuration transfer failed; no key was printed. Check device connection and unlock state.")
    print("DeepSeek configuration delivered; local temporary file removed. Launch the app to save it into Keychain.")


if __name__ == "__main__":
    main()
