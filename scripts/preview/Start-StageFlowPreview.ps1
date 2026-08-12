[CmdletBinding()]
param(
    [ValidateSet("Fixture", "Live")]
    [string]$Mode = "Fixture",

    [ValidatePattern("^[a-z0-9-]+$")]
    [string]$Scenario = "quiet",

    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 3000,

    [ValidateRange(1, 65535)]
    [int]$BackendPort = 8000
)

$ErrorActionPreference = "Stop"

function Resolve-RequiredCommand {
    param([Parameter(Mandatory)][string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "Required command '$Name' is not available on PATH."
    }
    return $command.Source
}

function Stop-OwnedProcess {
    param([System.Diagnostics.Process]$Process)

    if ($null -eq $Process) {
        return
    }

    $processIds = @($Process.Id)
    try {
        $snapshot = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId)
        $queue = [System.Collections.Generic.Queue[int]]::new()
        $seen = [System.Collections.Generic.HashSet[int]]::new()
        $queue.Enqueue($Process.Id)
        $processIds = @()

        while ($queue.Count -gt 0) {
            $processId = $queue.Dequeue()
            if (-not $seen.Add($processId)) {
                continue
            }
            $processIds += $processId
            foreach ($child in $snapshot | Where-Object ParentProcessId -eq $processId) {
                $queue.Enqueue([int]$child.ProcessId)
            }
        }
    }
    catch {
        Write-Warning "Could not enumerate preview descendants; stopping root process $($Process.Id)."
    }

    [array]::Reverse($processIds)
    foreach ($processId in $processIds) {
        Stop-Process -Id $processId -ErrorAction SilentlyContinue
    }
    $Process.WaitForExit(5000) | Out-Null
}

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$frontendRoot = Join-Path $repositoryRoot "frontend"
$backendRoot = Join-Path $repositoryRoot "backend"
$npm = Resolve-RequiredCommand "npm.cmd"
$ownedProcesses = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()

try {
    if ($Mode -eq "Live") {
        if ([string]::IsNullOrWhiteSpace($env:STAGEFLOW_KERNEL_CONFIG_PATH)) {
            throw "Live preview requires STAGEFLOW_KERNEL_CONFIG_PATH and its referenced DSN secret."
        }
        $uv = Resolve-RequiredCommand "uv.exe"
        $backend = Start-Process `
            -FilePath $uv `
            -ArgumentList @("run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", $BackendPort) `
            -WorkingDirectory $backendRoot `
            -NoNewWindow `
            -PassThru
        $ownedProcesses.Add($backend)
        $env:STAGEFLOW_UI_DATA_MODE = "kernel"
        $env:STAGEFLOW_KERNEL_STATUS_URL = "http://127.0.0.1:$BackendPort/api/v1/kernel/status"
        $env:STAGEFLOW_MTE_API_BASE_URL = "http://127.0.0.1:$BackendPort/api/v1"
    }
    else {
        $env:STAGEFLOW_UI_DATA_MODE = "fixture"
    }

    $frontend = Start-Process `
        -FilePath $npm `
        -ArgumentList @("run", "dev", "--", "--hostname", "127.0.0.1", "--port", $FrontendPort) `
        -WorkingDirectory $frontendRoot `
        -NoNewWindow `
        -PassThru
    $ownedProcesses.Add($frontend)

    $previewUrl = "http://127.0.0.1:$FrontendPort/?scenario=$Scenario"
    Write-Host "StageFlow $Mode preview starting at $previewUrl"
    Write-Host "Child output remains attached to this terminal. Press Ctrl+C to stop owned processes."

    while ($true) {
        foreach ($process in $ownedProcesses) {
            if ($process.HasExited) {
                throw "Preview child process $($process.Id) exited with code $($process.ExitCode)."
            }
        }
        Start-Sleep -Seconds 1
    }
}
finally {
    foreach ($process in $ownedProcesses) {
        Stop-OwnedProcess $process
    }
}
