<#
.SYNOPSIS
Runs the guarded StageFlow Demo hardware-rehearsal lifecycle.

.EXAMPLE
.\scripts\demo\StageFlow-Demo.ps1 prepare

.EXAMPLE
.\scripts\demo\StageFlow-Demo.ps1 start

.EXAMPLE
.\scripts\demo\StageFlow-Demo.ps1 publish-devcon
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet(
        "prepare", "start", "status", "diagnose", "stop",
        "rehearsal-report", "publish-devcon"
    )]
    [string]$Action,
    [string]$ConfigPath,
    [string]$CudaRuntimePath,
    [guid]$OperatorId,
    [string]$ProducerAddress,
    [string]$ReportPath,
    [switch]$ConfirmHumanAuthority
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$script:RepositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$script:BackendRoot = Join-Path $script:RepositoryRoot "backend"
$script:LauncherPath = Join-Path $PSScriptRoot "Start-StageFlowDemo.ps1"
$localAppData = [Environment]::GetFolderPath(
    [Environment+SpecialFolder]::LocalApplicationData
)
if ([string]::IsNullOrWhiteSpace($localAppData)) {
    throw "controller_local_application_data_unavailable"
}
$script:StateRoot = Join-Path $localAppData "StageFlowDemo\controller"
$script:StatePath = Join-Path $script:StateRoot "controller-state.json"
$script:StdoutPath = Join-Path $script:StateRoot "launcher.stdout.log"
$script:StderrPath = Join-Path $script:StateRoot "launcher.stderr.log"

function Get-ProcessOrUserValue {
    param([Parameter(Mandatory = $true)][string]$Name)
    $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = [Environment]::GetEnvironmentVariable($Name, "User")
    }
    return $value
}

function Import-RequiredSecret {
    param([Parameter(Mandatory = $true)][string]$Name)
    $value = Get-ProcessOrUserValue $Name
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "required_secret_unavailable: $Name (presence only)"
    }
    [Environment]::SetEnvironmentVariable($Name, $value, "Process")
}

function Resolve-ConfiguredFile {
    param(
        [string]$Requested,
        [Parameter(Mandatory = $true)][string]$EnvironmentName,
        [Parameter(Mandatory = $true)][string[]]$Candidates,
        [Parameter(Mandatory = $true)][string]$FailureCode
    )
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        if (-not (Test-Path -LiteralPath $Requested -PathType Leaf)) {
            throw $FailureCode
        }
        return [System.IO.Path]::GetFullPath($Requested)
    }
    $configured = Get-ProcessOrUserValue $EnvironmentName
    if (-not [string]::IsNullOrWhiteSpace($configured)) {
        if (-not (Test-Path -LiteralPath $configured -PathType Leaf)) {
            throw $FailureCode
        }
        return [System.IO.Path]::GetFullPath($configured)
    }
    $available = @($Candidates | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_) -and
        (Test-Path -LiteralPath $_ -PathType Leaf)
    } | ForEach-Object { [System.IO.Path]::GetFullPath($_) } | Select-Object -Unique)
    if ($available.Count -ne 1) { throw $FailureCode }
    return $available[0]
}

function Resolve-ConfiguredDirectory {
    param(
        [string]$Requested,
        [Parameter(Mandatory = $true)][string]$EnvironmentName,
        [Parameter(Mandatory = $true)][string[]]$Candidates,
        [Parameter(Mandatory = $true)][string]$FailureCode
    )
    $candidate = $Requested
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $candidate = Get-ProcessOrUserValue $EnvironmentName
    }
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $available = @($Candidates | Where-Object {
            Test-Path -LiteralPath $_ -PathType Container
        } | ForEach-Object { [System.IO.Path]::GetFullPath($_) } | Select-Object -Unique)
        if ($available.Count -ne 1) { throw $FailureCode }
        $candidate = $available[0]
    }
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
        throw $FailureCode
    }
    $resolved = [System.IO.Path]::GetFullPath($candidate)
    if (-not (Test-Path -LiteralPath (Join-Path $resolved "cublas64_12.dll") -PathType Leaf)) {
        throw "cuda_runtime_required_library_unavailable"
    }
    return $resolved
}

function Resolve-DemoConfiguration {
    $rootCandidates = @(
        "C:\StageFlowDemo\demo-single-stage.toml",
        "C:\StageFlowDemo\config\demo-single-stage.toml"
    )
    foreach ($directory in @("C:\StageFlowDemo", "C:\StageFlowDemo\config")) {
        if (Test-Path -LiteralPath $directory -PathType Container) {
            $rootCandidates += @(
                Get-ChildItem -LiteralPath $directory -Filter "*.toml" -File |
                    Select-Object -ExpandProperty FullName
            )
        }
    }
    return Resolve-ConfiguredFile -Requested $ConfigPath `
        -EnvironmentName "STAGEFLOW_DEMO_CONFIG_PATH" `
        -Candidates $rootCandidates `
        -FailureCode "demo_config_unavailable_or_ambiguous"
}

function Resolve-CudaRuntime {
    return Resolve-ConfiguredDirectory -Requested $CudaRuntimePath `
        -EnvironmentName "STAGEFLOW_DEMO_CUDA_RUNTIME_PATH" `
        -Candidates @("C:\StageFlowDemo\runtime\whisper-cuda-12.4\Release") `
        -FailureCode "demo_cuda_runtime_unavailable_or_ambiguous"
}

function Initialize-DemoEnvironment {
    Import-RequiredSecret "STAGEFLOW_DEMO_POSTGRES_DSN"
    $resolvedConfig = Resolve-DemoConfiguration
    $resolvedCuda = Resolve-CudaRuntime
    $env:STAGEFLOW_KERNEL_CONFIG_PATH = $resolvedConfig
    return [pscustomobject]@{
        ConfigPath = $resolvedConfig
        CudaRuntimePath = $resolvedCuda
    }
}

function Resolve-UvCommand {
    $command = Get-Command "uv" -ErrorAction SilentlyContinue
    if ($null -eq $command) { throw "required_tool_unavailable: uv" }
    return $command.Source
}

function Invoke-DemoPython {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$Capture
    )
    $uv = Resolve-UvCommand
    Push-Location $script:BackendRoot
    try {
        if ($Capture) {
            $output = & $uv run python -m app.demo.controller @Arguments
            if ($LASTEXITCODE -ne 0) { throw "demo_controller_python_failed" }
            return ($output -join "`n")
        }
        & $uv run python -m app.demo.controller @Arguments
        if ($LASTEXITCODE -ne 0) { throw "demo_controller_python_failed" }
    }
    finally {
        Pop-Location
    }
}

function Invoke-WithCudaRuntime {
    param(
        [Parameter(Mandatory = $true)][string]$RuntimePath,
        [Parameter(Mandatory = $true)][scriptblock]$Operation
    )
    $originalPath = $env:PATH
    try {
        $env:PATH = $RuntimePath + [System.IO.Path]::PathSeparator + $originalPath
        & $Operation
    }
    finally {
        $env:PATH = $originalPath
    }
}

function Resolve-OperatorIdentity {
    $candidate = $null
    if ($null -ne $OperatorId -and $OperatorId -ne [guid]::Empty) {
        $candidate = $OperatorId.ToString("D")
    }
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $candidate = Get-ProcessOrUserValue "STAGEFLOW_DEMO_OPERATOR_ID"
    }
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $candidate = Invoke-DemoPython -Arguments @("operator-id") -Capture
    }
    $parsed = [guid]::Empty
    if (-not [guid]::TryParse($candidate.Trim(), [ref]$parsed) -or $parsed -eq [guid]::Empty) {
        throw "demo_operator_identity_unavailable_or_ambiguous"
    }
    return $parsed
}

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Read-ControllerState {
    if (-not (Test-Path -LiteralPath $script:StatePath -PathType Leaf)) { return $null }
    try {
        return Get-Content -LiteralPath $script:StatePath -Raw -Encoding UTF8 |
            ConvertFrom-Json
    }
    catch {
        throw "controller_state_invalid"
    }
}

function Test-RecordedLauncherLive {
    param($State)
    if ($null -eq $State -or $null -eq $State.launcher_pid) { return $false }
    $process = Get-Process -Id ([int]$State.launcher_pid) -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $false }
    $recordedStart = [DateTimeOffset]$State.launcher_started_at
    return $process.StartTime.ToUniversalTime().Ticks -eq
        $recordedStart.UtcDateTime.Ticks
}

function Start-DemoStack {
    param($Configuration)
    New-Item -ItemType Directory -Path $script:StateRoot -Force | Out-Null
    $existing = Read-ControllerState
    if (Test-RecordedLauncherLive $existing) { throw "controller_launcher_already_running" }
    foreach ($port in @(8000, 3000)) {
        if (@(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue).Count -gt 0) {
            throw "controller_required_port_in_use: $port"
        }
    }
    Invoke-DemoPython -Arguments @("verify-database") | Out-Null
    $operator = Resolve-OperatorIdentity
    $hostProcess = Get-Process -Id $PID
    $powerShellPath = $hostProcess.Path
    $arguments = @(
        "-NoProfile",
        "-File", ('"{0}"' -f $script:LauncherPath),
        "-ConfigPath", ('"{0}"' -f $Configuration.ConfigPath),
        "-OperatorId", $operator.ToString("D"),
        "-CudaRuntimePath", ('"{0}"' -f $Configuration.CudaRuntimePath)
    )
    if (-not [string]::IsNullOrWhiteSpace($ProducerAddress)) {
        $arguments += @("-ProducerAddress", $ProducerAddress)
    }
    $process = Start-Process -FilePath $powerShellPath -ArgumentList $arguments `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $script:StdoutPath `
        -RedirectStandardError $script:StderrPath
    $state = [ordered]@{
        schema_version = "1.0"
        status = "starting"
        launcher_pid = $process.Id
        launcher_started_at = $process.StartTime.ToUniversalTime().ToString("o")
        executable = $powerShellPath
        config_path = $Configuration.ConfigPath
        cuda_runtime_path = $Configuration.CudaRuntimePath
        frontend_url = $null
        started_at = [DateTimeOffset]::UtcNow.ToString("o")
    }
    Write-Utf8NoBom -Path $script:StatePath `
        -Content (($state | ConvertTo-Json -Depth 4) + "`n")
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds(180)
    while ([DateTimeOffset]::UtcNow -lt $deadline) {
        if ($process.HasExited) { throw "demo_launcher_exited_before_ready" }
        try {
            $health = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" `
                -UseBasicParsing -TimeoutSec 2
            if ($health.StatusCode -eq 200 -and (Test-Path -LiteralPath $script:StdoutPath)) {
                $output = Get-Content -LiteralPath $script:StdoutPath -Raw -Encoding UTF8
                $ready = [regex]::Match(
                    $output,
                    'StageFlow Demo 1 is ready at (http://[^/\s]+:\d+/)'
                )
                if ($ready.Success) {
                    $state.status = "ready"
                    $state.frontend_url = $ready.Groups[1].Value
                    Write-Utf8NoBom -Path $script:StatePath `
                        -Content (($state | ConvertTo-Json -Depth 4) + "`n")
                    "StageFlow Demo ready: $($state.frontend_url)"
                    "Backend: loopback only"
                    return
                }
            }
        }
        catch { }
        Start-Sleep -Milliseconds 500
    }
    throw "demo_launcher_readiness_timeout"
}

function Stop-DemoStack {
    $state = Read-ControllerState
    if (-not (Test-RecordedLauncherLive $state)) {
        "StageFlow Demo controller: no recorded live launcher."
        return
    }
    $rootId = [int]$state.launcher_pid
    $snapshot = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId)
    $queue = [System.Collections.Generic.Queue[int]]::new()
    $seen = [System.Collections.Generic.HashSet[int]]::new()
    $queue.Enqueue($rootId)
    $processIds = @()
    while ($queue.Count -gt 0) {
        $processId = $queue.Dequeue()
        if (-not $seen.Add($processId)) { continue }
        $processIds += $processId
        foreach ($child in $snapshot | Where-Object ParentProcessId -eq $processId) {
            $queue.Enqueue([int]$child.ProcessId)
        }
    }
    [array]::Reverse($processIds)
    foreach ($processId in $processIds) {
        Stop-Process -Id $processId -ErrorAction SilentlyContinue
    }
    $state.status = "stopped"
    $state | Add-Member -NotePropertyName "stopped_at" -NotePropertyValue ([DateTimeOffset]::UtcNow.ToString("o")) -Force
    Write-Utf8NoBom -Path $script:StatePath `
        -Content (($state | ConvertTo-Json -Depth 4) + "`n")
    "StageFlow Demo controller: owned launcher stopped."
}

function Show-DemoStatus {
    $payload = Invoke-DemoPython -Arguments @("status") -Capture | ConvertFrom-Json
    "STAGEFLOW DEMO STATUS"
    "Event: $($payload.event.event_key) [$($payload.event.event_id)]"
    "Stage: $($payload.stage.stage_key) [$($payload.stage.stage_id)]"
    if ($null -eq $payload.session) {
        "Session: NONE"
    }
    else {
        "Session: $($payload.session.session_id) ($($payload.session.activity_state))"
        "Package: $($payload.package.state) revision=$($payload.package.revision) approved=$($payload.package.approved)"
    }
    "Media: registered=$($payload.media.registered) associated=$($payload.media.associated) stabilizing=$($payload.media.stabilizing) unresolved=$($payload.media.unresolved) conflicting=$($payload.media.conflicting)"
    $operationPairs = @($payload.operations.counts.PSObject.Properties |
        ForEach-Object { "$($_.Name)=$($_.Value)" })
    "Operations: $($operationPairs -join ', ')"
    "Terminal failures: $(@($payload.operations.terminal_failures).Count)"
    "Worker: $($payload.worker.state) available=$($payload.worker.available)"
    "Transcription Evidence: complete=$($payload.transcript_evidence.complete) total=$($payload.transcript_evidence.count) (evidence only)"
    "Moments: $($payload.moments.count)"
    "Devcon cached expectations: $($payload.devcon.cached_program_expectations)"
}

function Publish-Devcon {
    $apiKey = Get-ProcessOrUserValue "STAGEFLOW_DEMO_DEVCON_API_KEY"
    if (-not [string]::IsNullOrWhiteSpace($apiKey)) {
        $env:STAGEFLOW_DEMO_DEVCON_API_KEY = $apiKey
    }
    $preview = Invoke-DemoPython -Arguments @("publish-preview") -Capture |
        ConvertFrom-Json
    "DEVCON PUBLISH"
    ""
    "Event:"
    $preview.event
    ""
    "Target session:"
    $preview.target_session
    ""
    "Fields:"
    @($preview.fields) | ForEach-Object { $_ }
    ""
    "Remote identity verified: $(if ($preview.remote_identity_verified) { 'YES' } else { 'NO' })"
    "Package approved: $(if ($preview.package_approved) { 'YES' } else { 'NO' })"
    "Credential available: $(if ($preview.credential_available) { 'YES' } else { 'NO' })"
    if (-not $preview.credential_available) {
        throw "required_secret_unavailable: STAGEFLOW_DEMO_DEVCON_API_KEY (presence only)"
    }
    $confirmed = $ConfirmHumanAuthority.IsPresent
    if (-not $confirmed) {
        $answer = Read-Host "Publish this StageFlow enrichment to Devcon? [y/N]"
        $confirmed = $answer -in @("y", "Y", "yes", "YES", "Yes")
    }
    if (-not $confirmed) {
        "Devcon publish cancelled; no PUT was sent."
        return
    }
    $result = Invoke-DemoPython -Arguments @(
        "publish", "--expected-digest", [string]$preview.candidate_digest, "--confirmed"
    ) -Capture | ConvertFrom-Json
    "Devcon write accepted: $(if ($result.write_accepted) { 'YES' } else { 'NO' })"
    "Devcon durable Git persistence verified: $(if ($result.durable_persistence_verified) { 'YES' } else { 'NO' })"
    "Devcon public API convergence: $([string]$result.public_api_state)"
    "Devcon publication status: $([string]$result.publication_status)"
}

$configuration = $null
try {
    if ($Action -eq "stop") {
        Stop-DemoStack
        exit 0
    }
    $configuration = Initialize-DemoEnvironment
    switch ($Action) {
        "prepare" {
            Invoke-WithCudaRuntime -RuntimePath $configuration.CudaRuntimePath -Operation {
                Invoke-DemoPython -Arguments @("prepare")
            }
        }
        "start" { Start-DemoStack $configuration }
        "status" { Show-DemoStatus }
        "diagnose" {
            Invoke-DemoPython -Arguments @("verify-database") | Out-Null
            Invoke-WithCudaRuntime -RuntimePath $configuration.CudaRuntimePath -Operation {
                Push-Location $script:BackendRoot
                try {
                    $uv = Resolve-UvCommand
                    & $uv run --group transcription python -m app.demo.cli preflight
                    if ($LASTEXITCODE -ne 0) { throw "demo_diagnose_preflight_failed" }
                }
                finally { Pop-Location }
            }
            "Demo diagnosis passed: config present, Demo database verified, CUDA inference available, Devcon GET available."
        }
        "rehearsal-report" {
            if ([string]::IsNullOrWhiteSpace($ReportPath)) {
                New-Item -ItemType Directory -Path $script:StateRoot -Force | Out-Null
                $ReportPath = Join-Path $script:StateRoot (
                    "rehearsal-report-{0}.json" -f [DateTimeOffset]::UtcNow.ToString("yyyyMMdd-HHmmss")
                )
            }
            Invoke-DemoPython -Arguments @("rehearsal-report", "--output", $ReportPath) | Out-Null
            "Sanitized rehearsal report written."
        }
        "publish-devcon" { Publish-Devcon }
    }
}
finally {
    $env:STAGEFLOW_DEMO_DEVCON_API_KEY = $null
}
