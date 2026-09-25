from __future__ import annotations

import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
CONTROLLER = ROOT / "scripts/demo/StageFlow-Demo.ps1"
LAUNCHER = ROOT / "scripts/demo/Start-StageFlowDemo.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
@pytest.mark.parametrize("action", ["publish-devcon", "PUBLISH-DEVCON"])
def test_frozen_publication_refuses_before_network_or_process_work(action: str) -> None:
    assert POWERSHELL is not None
    script = str(CONTROLLER).replace("'", "''")
    command = "\n".join(
        f"function {name} {{ throw 'FORBIDDEN_SIDE_EFFECT:{name}' }}"
        for name in ("Invoke-WebRequest", "Invoke-RestMethod", "Start-Process", "uv", "python")
    )
    command += (
        # Invoke the parsed script in memory so this test also works on hosts that
        # prohibit .ps1 file execution, without changing their execution policy.
        f"\n$controller = [scriptblock]::Create([IO.File]::ReadAllText('{script}'))"
        f"\ntry {{ & $controller -Action '{action}'; exit 0 }}"
        " catch { Write-Output $_.Exception.Message; exit 1 }"
    )
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, timeout=30, check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "External publication is frozen under ADR-0031" in output
    assert "awaiting Delivery design" in output
    assert "FORBIDDEN_SIDE_EFFECT" not in output


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required")
@pytest.mark.parametrize("path", [CONTROLLER, LAUNCHER], ids=["controller", "launcher"])
def test_powershell_scripts_parse(path: Path) -> None:
    assert POWERSHELL is not None
    escaped = str(path).replace("'", "''")
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command",
         "$tokens = $null; $errors = $null; "
         f"[void][System.Management.Automation.Language.Parser]::ParseFile('{escaped}', "
         "[ref]$tokens, [ref]$errors); "
         "if ($errors.Count) { $errors | Out-String | Write-Output; exit 1 }; exit 0"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_neutral_readiness_output_matches_controller_detection() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    emitted = re.search(r'Write-Host "(StageFlow is ready at [^"\n]+)"', launcher)
    pattern = re.search(r"'(StageFlow is ready at [^'\n]+)'", controller)
    assert emitted is not None and pattern is not None
    for address, port in (("192.0.2.10", "3000"), ("producer.example", "3456")):
        output = emitted[1].replace("${producerIp}", address).replace("$FrontendPort", port)
        matched = re.search(pattern[1], f"startup\n{output}\nProfile: demo-single-stage")
        assert matched is not None
        assert matched[1] == f"http://{address}:{port}/"
    assert "StageFlow Demo 1 is ready" not in launcher + controller


@pytest.mark.parametrize("example", [
    "demo-single-stage.toml.example", "demo2-autonomous-event-node.toml.example",
])
def test_default_example_uses_matching_local_schedule_and_placeholder_identity(
    example: str,
) -> None:
    text = (ROOT / "examples" / example).read_text()
    config = tomllib.loads(text)
    assert config["node_id"] == "example-node"
    assert config["event"]["external_references"] == {"external_event_id": "example-event"}
    assert config["event"]["stages"][0]["external_references"] == {"external_room_id": "main"}
    if example.startswith("demo2"):
        assert not re.search(r"devcon|razer|wenceslas", text, re.IGNORECASE)
    schedule = json.loads((ROOT / "examples/local-schedule.example.json").read_text())
    assert config["deployment_id"] == "example-deployment"
    assert config["event"]["name"] == "Example Event"
    assert config["event"]["key"] == schedule["event_key"]
    assert config["event"]["stages"][0]["key"] == schedule["sessions"][0]["stage_key"]
    assert config["local_schedule"] == {"path": "C:/StageFlowDemo/local-schedule.json"}
    assert config["schedule_source_reference"] == config["local_schedule"]["path"]
    assert "devcon_read" not in config
