[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ConfigPath,
    [Parameter(Mandatory)]
    [guid]$OperatorId,
    [Parameter(Mandatory)]
    [string]$CudaRuntimePath,
    [string]$ProducerAddress,
    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 3000,
    [ValidateRange(1, 65535)]
    [int]$BackendPort = 8000
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-RequiredCommand {
    param([Parameter(Mandatory)][string]$Name)
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "Required command '$Name' is not available on PATH."
    }
    return $command.Source
}

function Assert-PortAvailable {
    param([Parameter(Mandatory)][int]$Port)
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($null -ne $listener) {
        throw "Required port $Port is already in use."
    }
}

function Resolve-ProducerAddress {
    param([string]$RequestedAddress)
    if (-not [string]::IsNullOrWhiteSpace($RequestedAddress)) {
        $parsed = [System.Net.IPAddress]::None
        if (-not [System.Net.IPAddress]::TryParse($RequestedAddress, [ref]$parsed)) {
            throw "ProducerAddress must be an IPv4 address assigned to this machine."
        }
        if ($parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or
            [System.Net.IPAddress]::IsLoopback($parsed)) {
            throw "ProducerAddress must be a non-loopback IPv4 address."
        }
        $assigned = Get-NetIPAddress -AddressFamily IPv4 -IPAddress $RequestedAddress -ErrorAction SilentlyContinue
        if ($null -eq $assigned) {
            throw "ProducerAddress is not assigned to this machine."
        }
        return $RequestedAddress
    }
    $candidate = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.AddressState -eq "Preferred" -and
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -notlike "169.254.*"
        } |
        Sort-Object InterfaceMetric, SkipAsSource |
        Select-Object -First 1
    if ($null -eq $candidate) {
        throw "No preferred non-loopback IPv4 address is available. Supply -ProducerAddress after connecting the demo LAN."
    }
    return $candidate.IPAddress
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
        Write-Warning "Could not enumerate demo descendants; stopping root process $($Process.Id)."
    }
    [array]::Reverse($processIds)
    foreach ($processId in $processIds) {
        Stop-Process -Id $processId -ErrorAction SilentlyContinue
    }
    $Process.WaitForExit(5000) | Out-Null
}

function Wait-HttpReady {
    param(
        [Parameter(Mandatory)][string]$Url,
        [Parameter(Mandatory)][string]$Name
    )
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds(60)
    while ([DateTimeOffset]::UtcNow -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "$Name did not become ready within 60 seconds."
}

function New-DemoLaunchContext {
    $bytes = [byte[]]::new(32)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$backendRoot = Join-Path $repositoryRoot "backend"
$frontendRoot = Join-Path $repositoryRoot "frontend"
$resolvedConfigPath = [System.IO.Path]::GetFullPath($ConfigPath)
if (-not (Test-Path -LiteralPath $resolvedConfigPath -PathType Leaf)) {
    throw "ConfigPath must name an existing file."
}
if ([string]::IsNullOrWhiteSpace($CudaRuntimePath)) {
    throw "CudaRuntimePath must name the isolated Demo CUDA runtime directory."
}
$resolvedCudaRuntimePath = [System.IO.Path]::GetFullPath($CudaRuntimePath)
if (-not (Test-Path -LiteralPath $resolvedCudaRuntimePath -PathType Container)) {
    throw "CudaRuntimePath must name an existing directory."
}
foreach ($runtimeLibrary in @("cublas64_12.dll")) {
    $libraryPath = Join-Path $resolvedCudaRuntimePath $runtimeLibrary
    if (-not (Test-Path -LiteralPath $libraryPath -PathType Leaf)) {
        throw "CudaRuntimePath is missing required Demo runtime library '$runtimeLibrary'."
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot "node_modules") -PathType Container)) {
    throw "Frontend dependencies are missing. Run 'npm ci' in frontend first."
}

$uv = Resolve-RequiredCommand "uv.exe"
$npm = Resolve-RequiredCommand "npm.cmd"
Assert-PortAvailable $BackendPort
Assert-PortAvailable $FrontendPort
$producerIp = Resolve-ProducerAddress $ProducerAddress
$ownedProcesses = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()

$env:STAGEFLOW_KERNEL_CONFIG_PATH = $resolvedConfigPath
$env:STAGEFLOW_UI_DATA_MODE = "kernel"
$env:STAGEFLOW_KERNEL_STATUS_URL = "http://127.0.0.1:$BackendPort/api/v1/kernel/status"
$env:STAGEFLOW_MTE_API_BASE_URL = "http://127.0.0.1:$BackendPort/api/v1"
$env:STAGEFLOW_DEMO_API_BASE_URL = "http://127.0.0.1:$BackendPort/api/v1/demo"
$env:STAGEFLOW_DEMO_OPERATOR_ID = $OperatorId.ToString("D")
$originalPath = $env:PATH
$env:PATH = $resolvedCudaRuntimePath + [System.IO.Path]::PathSeparator + $originalPath

try {
    Push-Location $backendRoot
    try {
        & $uv run --group transcription python -m app.demo.cli preflight
        if ($LASTEXITCODE -ne 0) { throw "Demo preflight failed." }
        & $uv run --group transcription python -m app.demo.cli bootstrap
        if ($LASTEXITCODE -ne 0) { throw "Demo bootstrap failed." }
        & $uv run --group transcription python -m app.demo.cli sync-program
        if ($LASTEXITCODE -ne 0) { throw "Devcon program synchronization failed." }
    }
    finally {
        Pop-Location
    }

    $backendParameters = @{
        FilePath = $uv
        ArgumentList = @("run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", $BackendPort)
        WorkingDirectory = $backendRoot
        NoNewWindow = $true
        PassThru = $true
    }
    $backend = Start-Process @backendParameters
    $ownedProcesses.Add($backend)

    $workerParameters = @{
        FilePath = $uv
        ArgumentList = @("run", "--group", "transcription", "python", "-m", "app.demo.worker")
        WorkingDirectory = $backendRoot
        NoNewWindow = $true
        PassThru = $true
    }
    $worker = Start-Process @workerParameters
    $ownedProcesses.Add($worker)

    $frontendParameters = @{
        FilePath = $npm
        ArgumentList = @("run", "dev", "--", "--hostname", $producerIp, "--port", $FrontendPort)
        WorkingDirectory = $frontendRoot
        NoNewWindow = $true
        PassThru = $true
        Environment = @{
            STAGEFLOW_DEMO_LAUNCH_CONTEXT = (New-DemoLaunchContext)
        }
    }
    $frontend = Start-Process @frontendParameters
    $ownedProcesses.Add($frontend)

    Wait-HttpReady "http://127.0.0.1:$BackendPort/api/v1/health" "Backend"
    Wait-HttpReady "http://${producerIp}:$FrontendPort/" "Producer UI"

    Write-Host "StageFlow Demo 1 is ready at http://${producerIp}:$FrontendPort/"
    Write-Host "Profile: demo-single-stage (not Event-readiness certified)"
    Write-Host "Backend: loopback only; PostgreSQL is not exposed by this launcher."
    Write-Host "Devcon program: cached locally after the successful startup sync."
    Write-Host "Press Ctrl+C to stop only the processes owned by this launcher."

    while ($true) {
        foreach ($process in $ownedProcesses) {
            if ($process.HasExited) {
                throw "Demo child process $($process.Id) exited with code $($process.ExitCode)."
            }
        }
        Start-Sleep -Seconds 1
    }
}
finally {
    $env:PATH = $originalPath
    foreach ($process in $ownedProcesses) {
        Stop-OwnedProcess $process
    }
}
