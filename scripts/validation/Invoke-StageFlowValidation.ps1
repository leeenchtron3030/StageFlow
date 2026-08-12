<#
.SYNOPSIS
Runs bounded, non-production StageFlow real-event validation actions safely.

.DESCRIPTION
This controller derives one external Run workspace and invokes the existing
backend/tests/qualification/real_event_playback.py runner. It does not implement
Kernel behavior, create databases, control vMix, or run an unbounded loop.

.EXAMPLE
Invoke-StageFlowValidation.ps1 -Run 3 -Action Prepare

.EXAMPLE
Invoke-StageFlowValidation.ps1 -Run 3 -Action StartSession -SessionLabel session-a `
  -Title "Session A" -ConfirmHumanAuthority

.EXAMPLE
Invoke-StageFlowValidation.ps1 -Run 3 -Action Status
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 999)]
    [int]$Run,

    [Parameter(Mandatory = $true)]
    [ValidateSet(
        "Prepare", "ShowPaths", "Initialize", "Migrate", "Bootstrap", "Expectation",
        "StartSession", "Cycle", "DriveCycles", "EndSession", "Status",
        "Checkpoint", "Reconcile", "AssignAsset", "PackageReady", "CompletePackage",
        "RecordStop", "Reconstruct"
    )]
    [string]$Action,

    [string]$ValidationRoot = $env:STAGEFLOW_VALIDATION_ROOT,
    [string]$DatabaseEnvironmentVariable = "STAGEFLOW_VALIDATION_DSN",
    [string]$UvPath = "uv",
    [string]$PsqlPath,
    [string]$StageKey = "main",
    [string]$SessionLabel = "main",
    [string]$ExpectationKey,
    [string]$Title,
    [string[]]$Speaker = @(),
    [string]$PlannedStart,
    [string]$PlannedEnd,
    [string]$At = "now",
    [string]$Reason,
    [string]$AssetId,
    [ValidateSet("Approve", "Reject")]
    [string]$Decision,
    [ValidateRange(0, 3600)]
    [double]$CycleEverySeconds = 2,
    [ValidateRange(1, 10000)]
    [int]$MaxCycles = 60,
    [ValidateRange(30, 86400)]
    [int]$InteractiveExecutionBudgetSeconds = 180,
    [string]$Scope = "validation-live",
    [switch]$TurnoverGuard,
    [ValidateSet("SessionA", "SessionB")]
    [string]$TurnoverPhase,
    [string]$PredecessorSessionLabel,
    [string]$CorpusItem,
    [switch]$IncludeFilenames,
    [switch]$ConfirmHumanAuthority,
    [switch]$ConfirmAttentionReviewed,
    [switch]$Offline,
    [switch]$DryRun
)

# Capture qualification human authority before controller guards, configuration reads,
# process startup, or other potentially slow work. Explicit timestamps remain verbatim.
$script:AuthorityAt = $At
if ($Action -in @("StartSession", "EndSession") -and $At -eq "now") {
    $script:AuthorityAt = [DateTimeOffset]::UtcNow.ToString("o")
}

$ErrorActionPreference = "Stop"
$script:ControllerExitCode = 1
$script:RunLockStream = $null
$script:PreviousLockToken = $null
$script:PreviousLockPath = $null
$script:SessionLabelExplicit = $PSBoundParameters.ContainsKey("SessionLabel")

function Get-NormalizedFullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
}

function Test-PathInside {
    param(
        [Parameter(Mandatory = $true)][string]$Candidate,
        [Parameter(Mandatory = $true)][string]$Parent
    )
    $candidatePath = Get-NormalizedFullPath $Candidate
    $parentPath = Get-NormalizedFullPath $Parent
    $prefix = $parentPath + [System.IO.Path]::DirectorySeparatorChar
    return $candidatePath.Equals($parentPath, [System.StringComparison]::OrdinalIgnoreCase) -or
        $candidatePath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-ValidationPaths {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][int]$RunNumber
    )
    $token = "run-{0:D3}" -f $RunNumber
    return [pscustomobject]@{
        Token = $token
        Root = $Root
        Config = Join-Path $Root ("kernel-{0}.toml" -f $token)
        RunFile = Join-Path $Root ("{0}.json" -f $token)
        Summary = Join-Path $Root ("{0}.md" -f $token)
        Environment = Join-Path $Root ("{0}.environment.json" -f $token)
        OperationLock = Join-Path $Root ("{0}.operation.lock" -f $token)
        OperationLockMetadata = Join-Path $Root ("{0}.operation.lock.json" -f $token)
        Media = Join-Path (Join-Path $Root "media") $token
        EventKey = "real-event-validation-{0}" -f $token
        DeploymentId = "stageflow-validation-{0}" -f $token
        NodeId = "stageflow-validation-node-{0}" -f $token
        DatabaseName = "stageflow_validation_{0:D3}" -f $RunNumber
    }
}

function Get-RunLockDiagnostic {
    param([Parameter(Mandatory = $true)][string]$Path)
    try {
        $metadata = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
        $action = if ($metadata.action) { [string]$metadata.action } else { "unknown" }
        $processId = if ($metadata.runner_pid) {
            [string]$metadata.runner_pid
        }
        elseif ($metadata.controller_pid) {
            [string]$metadata.controller_pid
        }
        else { "unknown" }
        $startedAt = if ($metadata.started_at) {
            [string]$metadata.started_at
        }
        else { "unknown" }
        return "action=$action pid=$processId started_at=$startedAt"
    }
    catch {
        return "action=unknown pid=unknown started_at=unknown"
    }
}

function Enter-RunOperationLock {
    param(
        [Parameter(Mandatory = $true)]$Paths,
        [Parameter(Mandatory = $true)][string]$Operation
    )
    if ($DryRun -or $script:RunLockStream) { return }
    New-Item -ItemType Directory -Path $Paths.Root -Force | Out-Null
    $stream = $null
    $controllerLocked = $false
    try {
        $stream = New-Object System.IO.FileStream(
            $Paths.OperationLock,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::ReadWrite
        )
        if ($stream.Length -lt 2) {
            $stream.SetLength(2)
            $stream.Flush($true)
        }
        $stream.Lock(0, 1)
        $controllerLocked = $true
        try {
            $stream.Lock(1, 1)
            $stream.Unlock(1, 1)
        }
        catch {
            throw [System.IO.IOException]::new("runner_region_locked")
        }
        $token = [Guid]::NewGuid().ToString("N")
        $metadata = [ordered]@{
            schema_version = "1.0"
            action = $Operation
            controller_pid = $PID
            runner_pid = $null
            started_at = [DateTimeOffset]::UtcNow.ToString("o")
            run_file = $Paths.RunFile
            token = $token
        }
        Write-Utf8NoBom -Path $Paths.OperationLockMetadata `
            -Content (($metadata | ConvertTo-Json -Depth 4) + "`n")
        $script:PreviousLockToken = [Environment]::GetEnvironmentVariable(
            "STAGEFLOW_VALIDATION_CONTROLLER_LOCK_TOKEN", "Process"
        )
        $script:PreviousLockPath = [Environment]::GetEnvironmentVariable(
            "STAGEFLOW_VALIDATION_CONTROLLER_LOCK_PATH", "Process"
        )
        $env:STAGEFLOW_VALIDATION_CONTROLLER_LOCK_TOKEN = $token
        $env:STAGEFLOW_VALIDATION_CONTROLLER_LOCK_PATH = $Paths.OperationLock
        $script:RunLockStream = $stream
    }
    catch {
        if ($controllerLocked -and $stream) {
            try { $stream.Unlock(0, 1) } catch { }
        }
        if ($stream) { $stream.Dispose() }
        $diagnostic = Get-RunLockDiagnostic $Paths.OperationLockMetadata
        throw "qualification_operation_already_active: $diagnostic; WAIT FOR ACTIVE QUALIFICATION OPERATION; HOST TIMEOUT DOES NOT PROVE CHILD TERMINATION"
    }
}

function Exit-RunOperationLock {
    if ($script:RunLockStream) {
        try { $script:RunLockStream.Unlock(0, 1) } catch { }
        $script:RunLockStream.Dispose()
        $script:RunLockStream = $null
    }
    [Environment]::SetEnvironmentVariable(
        "STAGEFLOW_VALIDATION_CONTROLLER_LOCK_TOKEN",
        $script:PreviousLockToken,
        "Process"
    )
    [Environment]::SetEnvironmentVariable(
        "STAGEFLOW_VALIDATION_CONTROLLER_LOCK_PATH",
        $script:PreviousLockPath,
        "Process"
    )
}

function Assert-ValidationBoundary {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][int]$RunNumber
    )
    if ($RunNumber -lt 3) {
        throw "protected_baseline_run: this controller permits Run 003 and later only"
    }
    if (Test-PathInside -Candidate $Root -Parent $RepositoryRoot) {
        throw "validation_root_must_be_outside_repository"
    }
    $segments = (Get-NormalizedFullPath $Root) -split '[\\/]+'
    if (-not ($segments | Where-Object { $_ -eq "stageflow-validation" })) {
        throw "validation_root_must_include_stageflow-validation_directory"
    }
}

function Resolve-UvCommand {
    param([Parameter(Mandatory = $true)][string]$Requested)
    if (Test-Path -LiteralPath $Requested -PathType Leaf) {
        return (Get-NormalizedFullPath $Requested)
    }
    $command = Get-Command $Requested -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "required_tool_missing: uv"
    }
    return $command.Source
}

function Resolve-GitCommand {
    $command = Get-Command "git" -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        throw "required_tool_missing: git"
    }
    return $command.Source
}

function Resolve-PsqlCommand {
    param([string]$Requested)
    if ($Requested) {
        if (Test-Path -LiteralPath $Requested -PathType Leaf) {
            return (Get-NormalizedFullPath $Requested)
        }
        $requestedCommand = Get-Command $Requested -ErrorAction SilentlyContinue
        if ($null -ne $requestedCommand) {
            return $requestedCommand.Source
        }
        throw "required_tool_missing: psql"
    }
    $command = Get-Command "psql" -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    $roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) |
        Where-Object { $_ } |
        ForEach-Object { Join-Path $_ "PostgreSQL" } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Container }
    foreach ($root in $roots) {
        $candidate = Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName "bin\psql.exe" } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
            Select-Object -First 1
        if ($candidate) {
            return $candidate
        }
    }
    throw "required_tool_missing: psql; install the PostgreSQL client or add it to PATH"
}

function Get-DatabaseConnectionParts {
    param(
        [Parameter(Mandatory = $true)][string]$ConnectionString,
        [Parameter(Mandatory = $true)][string]$ExpectedDatabase
    )
    try {
        $uri = [System.Uri]$ConnectionString
    }
    catch {
        throw "validation_database_connection_must_be_a_standard_postgresql_uri"
    }
    if ($uri.Scheme -notin @("postgres", "postgresql") -or -not $uri.IsAbsoluteUri) {
        throw "validation_database_connection_must_be_a_standard_postgresql_uri"
    }
    $database = [System.Uri]::UnescapeDataString($uri.AbsolutePath.TrimStart("/"))
    if (-not $database -or $database.Contains("/")) {
        throw "validation_database_name_missing"
    }
    if ($database -ne $ExpectedDatabase) {
        throw "validation_database_run_mismatch: expected $ExpectedDatabase"
    }
    $user = ""
    $password = ""
    $separator = $uri.UserInfo.IndexOf(":", [System.StringComparison]::Ordinal)
    if ($separator -ge 0) {
        $user = [System.Uri]::UnescapeDataString($uri.UserInfo.Substring(0, $separator))
        $password = [System.Uri]::UnescapeDataString($uri.UserInfo.Substring($separator + 1))
    }
    else {
        $user = [System.Uri]::UnescapeDataString($uri.UserInfo)
    }
    if (-not $uri.Host -or -not $user) {
        throw "validation_database_uri_requires_host_and_user"
    }
    $port = $uri.Port
    if ($port -lt 1) {
        $port = 5432
    }
    return [pscustomobject]@{
        Host = $uri.Host
        Port = $port
        User = $user
        Password = $password
        Database = $database
    }
}

function Invoke-DatabaseProbe {
    param(
        [Parameter(Mandatory = $true)]$Connection,
        [Parameter(Mandatory = $true)][string]$PsqlCommand
    )
    $names = @("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGCONNECT_TIMEOUT")
    $previous = @{}
    foreach ($name in $names) {
        $previous[$name] = [System.Environment]::GetEnvironmentVariable($name, "Process")
    }
    try {
        $env:PGHOST = $Connection.Host
        $env:PGPORT = [string]$Connection.Port
        $env:PGUSER = $Connection.User
        $env:PGPASSWORD = $Connection.Password
        $env:PGDATABASE = $Connection.Database
        $env:PGCONNECT_TIMEOUT = "5"
        $output = & $PsqlCommand -X --no-password --tuples-only --no-align `
            --command "SELECT current_database() || '|' || current_setting('server_version');" 2>&1
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            throw "validation_database_probe_failed: create and verify the isolated database, then retry"
        }
        $line = @($output | ForEach-Object { [string]$_ } | Where-Object { $_ -match "^[^|]+\|.+$" }) |
            Select-Object -Last 1
        if (-not $line) {
            throw "validation_database_probe_returned_unexpected_result"
        }
        $separator = $line.IndexOf("|", [System.StringComparison]::Ordinal)
        $database = $line.Substring(0, $separator)
        $serverVersion = $line.Substring($separator + 1)
        if ($database -ne $Connection.Database) {
            throw "validation_database_probe_identity_mismatch"
        }
        return [pscustomobject]@{
            Database = $database
            ServerVersion = $serverVersion
        }
    }
    finally {
        foreach ($name in $names) {
            [System.Environment]::SetEnvironmentVariable($name, $previous[$name], "Process")
        }
    }
}

function Quote-SafeArgument {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Write-RunnerPreview {
    param(
        [Parameter(Mandatory = $true)][string]$UvCommand,
        [Parameter(Mandatory = $true)][string]$RunnerPath,
        [Parameter(Mandatory = $true)][string[]]$RunnerArguments
    )
    $safe = @($UvCommand, "run", "python", $RunnerPath) + $RunnerArguments
    Write-Host ("DRY RUN: " + (($safe | ForEach-Object { Quote-SafeArgument ([string]$_) }) -join " "))
}

function Invoke-ValidationRunner {
    param(
        [Parameter(Mandatory = $true)][string]$UvCommand,
        [Parameter(Mandatory = $true)][string]$RunnerPath,
        [Parameter(Mandatory = $true)][string[]]$RunnerArguments,
        [switch]$Preview
    )
    if ($Preview) {
        Write-RunnerPreview -UvCommand $UvCommand -RunnerPath $RunnerPath `
            -RunnerArguments $RunnerArguments
        return
    }
    $backendRoot = Split-Path (Split-Path (Split-Path $RunnerPath -Parent) -Parent) -Parent
    Push-Location $backendRoot
    try {
        & $UvCommand run python $RunnerPath @RunnerArguments
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    if ($exitCode -ne 0) {
        $script:ControllerExitCode = $exitCode
        throw "validation_runner_failed_with_exit_code:$exitCode"
    }
}

function New-KernelConfiguration {
    param([Parameter(Mandatory = $true)]$Paths)
    $mediaPath = (Get-NormalizedFullPath $Paths.Media).Replace("\", "/")
    if ($mediaPath.Contains('"') -or $mediaPath.Contains("`n") -or $mediaPath.Contains("`r")) {
        throw "validation_media_path_cannot_be_represented_safely"
    }
    return @"
schema_version = "1.0"
deployment_id = "$($Paths.DeploymentId)"
node_id = "$($Paths.NodeId)"
node_role = "node"
event_mode = "event"
network_policy = "local_only"
postgres_dsn_secret_ref = "$DatabaseEnvironmentVariable"

[event]
key = "$($Paths.EventKey)"
name = "Real-Event Validation Run $($Run.ToString('D3'))"

[[event.stages]]
key = "main"
name = "Main Stage"

[[event.stages.sources]]
key = "main-source"
path = "$mediaPath"
maximum_candidates = 100
allowed_extensions = [".mp4"]

[resources]
maximum_concurrent_assessments = 2
maximum_cpu_percentage = 20
maximum_memory_bytes = 536870912
minimum_stable_seconds = 5
"@
}

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Get-ToolOutput {
    param([Parameter(Mandatory = $true)][scriptblock]$Command)
    try {
        return ((& $Command 2>$null) | ForEach-Object { [string]$_ }) -join " "
    }
    catch {
        return "unavailable"
    }
}

function Write-EnvironmentManifest {
    param(
        [Parameter(Mandatory = $true)]$Paths,
        [Parameter(Mandatory = $true)][string]$RepositoryRoot,
        [Parameter(Mandatory = $true)][string]$GitCommand,
        [Parameter(Mandatory = $true)][string]$UvCommand,
        [Parameter(Mandatory = $true)][string]$PsqlCommand,
        [Parameter(Mandatory = $true)]$DatabaseProbe
    )
    $gitCommit = Get-ToolOutput { & $GitCommand -C $RepositoryRoot rev-parse HEAD }
    $gitStatus = @(& $GitCommand -C $RepositoryRoot status --short 2>$null)
    $manifest = [ordered]@{
        schema_version = "1.0"
        recorded_at = [DateTimeOffset]::UtcNow.ToString("o")
        qualification_only = $true
        run = $Run
        run_token = $Paths.Token
        event_key = $Paths.EventKey
        stage_key = "main"
        database_name = $Paths.DatabaseName
        database_environment_variable = $DatabaseEnvironmentVariable
        media_directory = $Paths.Media
        cycle_every_seconds = $CycleEverySeconds
        maximum_cycles = $MaxCycles
        git_commit = $gitCommit.Trim()
        git_worktree_dirty = ($gitStatus.Count -gt 0)
        git_changed_path_count = $gitStatus.Count
        uv_version = Get-ToolOutput { & $UvCommand --version }
        python_version = Get-ToolOutput { & $UvCommand run python --version }
        psql_version = Get-ToolOutput { & $PsqlCommand --version }
        postgresql_server_version = $DatabaseProbe.ServerVersion
        powershell_version = $PSVersionTable.PSVersion.ToString()
        operating_system = [System.Environment]::OSVersion.VersionString
        notes = @(
            "No DSN or credential value is stored in this manifest.",
            "The controller does not create the database or control vMix."
        )
    }
    $json = $manifest | ConvertTo-Json -Depth 6
    Write-Utf8NoBom -Path $Paths.Environment -Content ($json + "`n")
}

function Read-RunState {
    param([Parameter(Mandatory = $true)][string]$RunFile)
    if (-not (Test-Path -LiteralPath $RunFile -PathType Leaf)) {
        throw "run_file_not_found"
    }
    try {
        return Get-Content -LiteralPath $RunFile -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        throw "run_file_unreadable"
    }
}

function Write-WaitingForHumanAuthority {
    Write-Host ("WAITING FOR HUMAN AUTHORITY {0} DO NOT CONTINUE MEDIA PROCEDURE" -f [char]0x2014)
}

function Get-RecordedSession {
    param(
        [Parameter(Mandatory = $true)]$State,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $property = $State.sessions.PSObject.Properties[$Label]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Write-TurnoverAuthorityState {
    param(
        [Parameter(Mandatory = $true)][string]$Phase,
        [Parameter(Mandatory = $true)][string]$ExpectedLabel,
        $Session,
        [string]$PredecessorLabel,
        $Predecessor
    )
    $activity = if ($Session) { [string]$Session.activity_state } else { "not_realized" }
    $start = if ($Session -and $Session.authoritative_start) { "present" } else { "absent" }
    $end = if ($Session -and $Session.authoritative_end) { "present" } else { "absent" }
    Write-Host "Turnover authority: phase=$Phase expected_session=$ExpectedLabel activity=$activity authoritative_start=$start authoritative_end=$end"
    if ($PredecessorLabel) {
        $predecessorActivity = if ($Predecessor) {
            [string]$Predecessor.activity_state
        }
        else { "not_realized" }
        $predecessorEnd = if ($Predecessor -and $Predecessor.authoritative_end) {
            "present"
        }
        else { "absent" }
        Write-Host "Turnover predecessor: session=$PredecessorLabel activity=$predecessorActivity authoritative_end=$predecessorEnd"
    }
}

function Assert-TurnoverPredecessorEnded {
    param([Parameter(Mandatory = $true)]$State)
    if (-not $PredecessorSessionLabel) {
        Write-WaitingForHumanAuthority
        throw "turnover_session_b_requires_predecessor_session_label"
    }
    $predecessor = Get-RecordedSession -State $State -Label $PredecessorSessionLabel
    if (-not $predecessor -or $predecessor.activity_state -ne "presentation_ended" -or
        -not $predecessor.authoritative_end) {
        Write-TurnoverAuthorityState -Phase $TurnoverPhase -ExpectedLabel $SessionLabel `
            -Session (Get-RecordedSession -State $State -Label $SessionLabel) `
            -PredecessorLabel $PredecessorSessionLabel -Predecessor $predecessor
        Write-WaitingForHumanAuthority
        throw "turnover_predecessor_requires_authoritative_presentation_end:$PredecessorSessionLabel"
    }
    return $predecessor
}

function Assert-GuardedDriveAuthority {
    param([Parameter(Mandatory = $true)]$Paths)
    if (-not $script:SessionLabelExplicit) {
        Write-WaitingForHumanAuthority
        throw "turnover_guard_requires_explicit_session_label"
    }
    $state = Read-RunState $Paths.RunFile
    $session = Get-RecordedSession -State $state -Label $SessionLabel
    $predecessor = $null
    if ($TurnoverPhase -eq "SessionB") {
        $predecessor = Assert-TurnoverPredecessorEnded -State $state
    }
    Write-TurnoverAuthorityState -Phase $TurnoverPhase -ExpectedLabel $SessionLabel `
        -Session $session -PredecessorLabel $PredecessorSessionLabel `
        -Predecessor $predecessor
    if (-not $session -or $session.activity_state -ne "presentation_active") {
        Write-WaitingForHumanAuthority
        throw "turnover_drive_requires_presentation_active:$SessionLabel"
    }
}

function Get-ObservedCandidateCount {
    param([Parameter(Mandatory = $true)]$State)
    $counts = @()
    $media = if ($State.media_blocks) {
        @($State.media_blocks.PSObject.Properties).Count
    }
    else { 0 }
    $counts += $media
    $latest = @($State.status_snapshots) | Select-Object -Last 1
    if ($latest) {
        if ($latest.reconciliation) {
            $counts += [int]$latest.reconciliation.candidates_seen
        }
        $stage = @($latest.stages | Where-Object { $_.stage_key -eq $StageKey }) |
            Select-Object -First 1
        if ($stage) {
            $counts += ([int]$stage.discovered + [int]$stage.stabilizing +
                [int]$stage.ready_media + [int]$stage.registered)
        }
    }
    return [int](($counts | Measure-Object -Maximum).Maximum)
}

function Get-ConfiguredSourceEntryEstimate {
    param([Parameter(Mandatory = $true)]$Paths)

    try {
        $configuration = Get-Content -LiteralPath $Paths.Config -Raw -Encoding UTF8
        $maximumMatches = [regex]::Matches(
            $configuration,
            '(?m)^\s*maximum_candidates\s*=\s*(\d+)\s*$'
        )
        $extensionMatches = [regex]::Matches(
            $configuration,
            '(?m)^\s*allowed_extensions\s*=\s*\[([^\]]*)\]\s*$'
        )
        if ($maximumMatches.Count -gt 1 -or $extensionMatches.Count -gt 1) {
            return [pscustomobject]@{ Count = 0; Status = "configuration_unavailable" }
        }

        $maximumCandidates = if ($maximumMatches.Count -eq 1) {
            [int]$maximumMatches[0].Groups[1].Value
        }
        else { 1000 }
        $allowed = New-Object 'System.Collections.Generic.HashSet[string]' (
            [System.StringComparer]::OrdinalIgnoreCase
        )
        if ($extensionMatches.Count -eq 1) {
            foreach ($match in [regex]::Matches(
                $extensionMatches[0].Groups[1].Value,
                '"([^"\\]*(?:\\.[^"\\]*)*)"'
            )) {
                $null = $allowed.Add($match.Groups[1].Value)
            }
        }
        else {
            foreach ($extension in @(".mov", ".mp4", ".mkv", ".mxf", ".wav")) {
                $null = $allowed.Add($extension)
            }
        }
        if ($maximumCandidates -lt 1 -or $allowed.Count -eq 0) {
            return [pscustomobject]@{ Count = 0; Status = "configuration_unavailable" }
        }

        $entries = @(
            Get-ChildItem -LiteralPath $Paths.Media -Force -ErrorAction Stop |
                Select-Object -First ($maximumCandidates + 1)
        )
        if ($entries.Count -gt $maximumCandidates) {
            return [pscustomobject]@{
                Count = $maximumCandidates
                Status = "inspection_bound_reached"
            }
        }

        $eligible = @($entries | Where-Object {
            $isReparsePoint = ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) `
                -ne 0
            $isExcludedName = $_.Name.StartsWith(".") -or
                $_.Name.EndsWith(".partial", [System.StringComparison]::OrdinalIgnoreCase) -or
                $_.Name.EndsWith(".tmp", [System.StringComparison]::OrdinalIgnoreCase)
            $extension = [System.IO.Path]::GetExtension($_.Name)
            (-not $_.PSIsContainer) -and (-not $isReparsePoint) -and
                (-not $isExcludedName) -and $allowed.Contains($extension)
        })
        return [pscustomobject]@{ Count = $eligible.Count; Status = "available" }
    }
    catch {
        return [pscustomobject]@{ Count = 0; Status = "source_unavailable" }
    }
}

function Assert-DriveCyclesWithinInteractiveBudget {
    param([Parameter(Mandatory = $true)]$Paths)
    $state = Read-RunState $Paths.RunFile
    $durableCandidateCount = Get-ObservedCandidateCount $state
    $sourceEstimate = Get-ConfiguredSourceEntryEstimate $Paths
    $candidateCount = [Math]::Max($durableCandidateCount, [int]$sourceEstimate.Count)
    $coreSeconds = 0.502 + (0.313 * $candidateCount)
    $startToStartSeconds = [Math]::Max($CycleEverySeconds, $coreSeconds)
    $conservativeCycleSeconds = $startToStartSeconds * 1.5
    $startupSeconds = 10.0
    $estimatedSeconds = $startupSeconds + ($MaxCycles * $conservativeCycleSeconds)
    $refusalThreshold = $InteractiveExecutionBudgetSeconds * 0.8
    $availableCycleSeconds = [Math]::Max(0.0, $refusalThreshold - $startupSeconds)
    $suggestedCycles = [Math]::Max(
        1,
        [Math]::Floor($availableCycleSeconds / $conservativeCycleSeconds)
    )
    Write-Host ([string]::Format(
        [System.Globalization.CultureInfo]::InvariantCulture,
        "Qualification runtime estimate: durable_candidates={0} source_eligible_entries={1} source_count_status={2} effective_candidates={3} cycles={4} cadence_seconds={5} estimated_seconds={6:F1} interactive_budget_seconds={7} suggested_max_cycles={8}",
        $durableCandidateCount,
        $sourceEstimate.Count,
        $sourceEstimate.Status,
        $candidateCount,
        $MaxCycles,
        $CycleEverySeconds,
        $estimatedSeconds,
        $InteractiveExecutionBudgetSeconds,
        $suggestedCycles
    ))
    if ($estimatedSeconds -ge $refusalThreshold) {
        throw ([string]::Format(
            [System.Globalization.CultureInfo]::InvariantCulture,
            "drive_cycles_estimated_runtime_exceeds_interactive_budget: estimated_seconds={0:F1} budget_seconds={1} suggested_max_cycles={2}; qualification telemetry only, not a production SLA",
            $estimatedSeconds,
            $InteractiveExecutionBudgetSeconds,
            $suggestedCycles
        ))
    }
}

function Write-TurnoverBoundaryCheckpoint {
    param([Parameter(Mandatory = $true)]$Paths)
    if (-not $TurnoverGuard -or $DryRun) { return }
    $state = Read-RunState $Paths.RunFile
    $session = Get-RecordedSession -State $state -Label $SessionLabel
    if ($Action -eq "StartSession" -and
        $session -and $session.activity_state -eq "presentation_active") {
        if ($TurnoverPhase -eq "SessionA") {
            Write-Host ("SESSION A ACTIVE {0} SAFE TO BEGIN RECORDING" -f [char]0x2014)
        }
        else {
            Write-Host ("SESSION B ACTIVE {0} SAFE TO CONTINUE TURNOVER INGEST" -f [char]0x2014)
        }
    }
    elseif ($Action -eq "EndSession" -and $session -and
        $session.activity_state -eq "presentation_ended" -and $session.authoritative_end) {
        if ($TurnoverPhase -eq "SessionA") {
            Write-Host ("SESSION A ENDED {0} KEEP RECORDING; WAITING FOR SESSION B AUTHORITY" -f [char]0x2014)
        }
        else {
            Write-Host ("SESSION B ENDED {0} SAFE TO STOP RECORDING" -f [char]0x2014)
        }
    }
}

function Assert-MatchingConfiguration {
    param([Parameter(Mandatory = $true)]$Paths)
    if (-not (Test-Path -LiteralPath $Paths.Config -PathType Leaf)) {
        throw "configuration_not_found: $($Paths.Config)"
    }
    $configuration = Get-Content -LiteralPath $Paths.Config -Raw -Encoding UTF8
    $sourceMatches = [regex]::Matches(
        $configuration,
        '(?m)^\s*path\s*=\s*"([^"]+)"\s*$'
    )
    $stageMatches = [regex]::Matches($configuration, '(?m)^\s*\[\[event\.stages\]\]\s*$')
    $bindingMatches = [regex]::Matches(
        $configuration,
        '(?m)^\s*\[\[event\.stages\.sources\]\]\s*$'
    )
    if ($sourceMatches.Count -ne 1 -or $stageMatches.Count -ne 1 -or $bindingMatches.Count -ne 1) {
        throw "configuration_must_have_exactly_one_stage_and_one_source"
    }
    $recordedSource = $sourceMatches[0].Groups[1].Value.Replace("\", "/")
    $expectedSource = (Get-NormalizedFullPath $Paths.Media).Replace("\", "/")
    if ($recordedSource -ne $expectedSource) {
        throw "configuration_media_path_run_mismatch"
    }
}

function Assert-MatchingRunArtifacts {
    param([Parameter(Mandatory = $true)]$Paths)
    Assert-MatchingConfiguration $Paths
    if (-not (Test-Path -LiteralPath $Paths.RunFile -PathType Leaf)) {
        throw "run_file_not_found: $($Paths.RunFile)"
    }
    $state = Read-RunState $Paths.RunFile
    if ($state.configuration.deployment_id -ne $Paths.DeploymentId) {
        throw "run_file_deployment_run_mismatch"
    }
    if ($state.configuration.event_key -ne $Paths.EventKey) {
        throw "run_file_event_run_mismatch"
    }
    return $state
}

function Show-ValidationSummary {
    param(
        [Parameter(Mandatory = $true)]$State,
        [Parameter(Mandatory = $true)]$Paths
    )
    $snapshots = @($State.status_snapshots)
    Write-Host "StageFlow validation checkpoint - $($Paths.Token)"
    Write-Host "Raw record: $($Paths.RunFile)"
    Write-Host "Markdown summary: $($Paths.Summary)"
    if ($snapshots.Count -eq 0 -or $null -eq $snapshots[-1]) {
        Write-Host "Result: no operational status snapshot has been recorded."
        return
    }
    $latest = $snapshots[-1]
    Write-Host ("Kernel: database_available={0} ready={1} recovering={2}" -f `
        $latest.database_available, $latest.ready, $latest.recovering)
    $stage = @($latest.stages | Where-Object { $_.stage_key -eq "main" }) | Select-Object -First 1
    if ($stage) {
        Write-Host ("Main Stage media: discovered={0} stabilizing={1} registered={2} associated={3} unresolved={4} conflicting={5}" -f `
            $stage.discovered, $stage.stabilizing, $stage.registered, $stage.associated, `
            $stage.unresolved, $stage.conflicting)
        Write-Host ("Main Stage projection: activity={0} package={1} package_revision={2}" -f `
            $stage.session_activity_state, $stage.session_package_state, $stage.session_package_revision)
    }
    foreach ($entry in @($State.sessions.PSObject.Properties | Sort-Object Name)) {
        $session = $entry.Value
        Write-Host ("Session {0}: activity={1} end={2} package={3} package_revision={4} revision={5}" -f `
            $entry.Name, $session.activity_state, $session.authoritative_end, `
            $session.package_state, $session.package_revision, $session.revision)
    }
    $attention = @($latest.attention_codes)
    if ($stage) {
        $attention += @($stage.attention_codes)
    }
    $attention = @($attention | Where-Object { $_ } | Sort-Object -Unique)
    $requiresReview = (-not $latest.database_available) -or (-not $latest.ready) -or
        $latest.recovering -or ($attention.Count -gt 0)
    if ($stage) {
        $requiresReview = $requiresReview -or ([int]$stage.stabilizing -gt 0) -or
            ([int]$stage.unresolved -gt 0) -or ([int]$stage.conflicting -gt 0)
    }
    if ($requiresReview) {
        $codes = if ($attention.Count -gt 0) { $attention -join ", " } else { "none" }
        Write-Host "Result: review required (attention codes: $codes)."
    }
    else {
        Write-Host "Result: checkpoint is quiet; no projected media or readiness exception requires review."
    }
}

function Assert-HumanAuthority {
    if (-not $ConfirmHumanAuthority) {
        throw "human_authority_confirmation_required: use -ConfirmHumanAuthority"
    }
}

function Assert-PackageReadyPreconditions {
    param([Parameter(Mandatory = $true)]$Paths)
    $state = Read-RunState $Paths.RunFile
    $property = $state.sessions.PSObject.Properties[$SessionLabel]
    if ($null -eq $property) {
        throw "session_label_not_found:$SessionLabel"
    }
    $session = $property.Value
    if ($session.activity_state -ne "presentation_ended" -or -not $session.authoritative_end) {
        throw "package_ready_requires_authoritative_presentation_end"
    }
    $latest = @($state.status_snapshots) | Select-Object -Last 1
    if ($null -eq $latest -or -not $latest.database_available -or -not $latest.ready -or $latest.recovering) {
        throw "package_ready_requires_fresh_ready_status; reconcile and checkpoint first"
    }
    $stage = @($latest.stages | Where-Object { $_.stage_key -eq $StageKey }) | Select-Object -First 1
    if ($null -eq $stage) {
        throw "package_ready_stage_status_missing:$StageKey"
    }
    $hasMediaConcern = ([int]$stage.stabilizing -gt 0) -or ([int]$stage.unresolved -gt 0) -or
        ([int]$stage.conflicting -gt 0) -or (@($stage.attention_codes).Count -gt 0)
    if ($hasMediaConcern -and -not $ConfirmAttentionReviewed) {
        throw "package_ready_media_review_required: inspect stabilizing, unresolved, conflicting, and attention state; use -ConfirmAttentionReviewed only after review"
    }
}

try {
    $repositoryRoot = Get-NormalizedFullPath (Join-Path $PSScriptRoot "..\..")
    $runnerPath = Join-Path $repositoryRoot "backend\tests\qualification\real_event_playback.py"
    if (-not (Test-Path -LiteralPath $runnerPath -PathType Leaf)) {
        throw "qualification_runner_not_found"
    }
    if (-not $ValidationRoot) {
        $desktop = [System.Environment]::GetFolderPath("Desktop")
        $ValidationRoot = Join-Path (Join-Path $desktop "StageFlow") "stageflow-validation"
    }
    $ValidationRoot = Get-NormalizedFullPath $ValidationRoot
    Assert-ValidationBoundary -Root $ValidationRoot -RepositoryRoot $repositoryRoot -RunNumber $Run
    $paths = Get-ValidationPaths -Root $ValidationRoot -RunNumber $Run

    if ($TurnoverGuard -and -not $TurnoverPhase) {
        throw "turnover_guard_requires_turnover_phase"
    }
    if (-not $TurnoverGuard -and ($TurnoverPhase -or $PredecessorSessionLabel)) {
        throw "turnover_phase_parameters_require_turnover_guard"
    }
    if ($TurnoverGuard -and $Action -notin @("StartSession", "EndSession", "DriveCycles")) {
        throw "turnover_guard_supported_only_for_session_boundaries_and_drive_cycles"
    }

    if ($Action -eq "ShowPaths") {
        $paths | Format-List
        return
    }
    if ($Offline) {
        if ($Action -notin @("Status", "Checkpoint")) {
            throw "offline_is_supported_only_for_status_or_checkpoint"
        }
        Show-ValidationSummary -State (Read-RunState $paths.RunFile) -Paths $paths
        return
    }

    $connectionString = [System.Environment]::GetEnvironmentVariable(
        $DatabaseEnvironmentVariable,
        "Process"
    )
    if (-not $connectionString) {
        throw "validation_database_environment_variable_unresolved:$DatabaseEnvironmentVariable"
    }
    if ($DatabaseEnvironmentVariable -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
        throw "validation_database_environment_variable_name_invalid"
    }
    $connection = Get-DatabaseConnectionParts -ConnectionString $connectionString `
        -ExpectedDatabase $paths.DatabaseName
    $uvCommand = Resolve-UvCommand $UvPath

    if ($Action -eq "Prepare") {
        foreach ($path in @($paths.Config, $paths.RunFile, $paths.Summary, $paths.Environment)) {
            if (Test-Path -LiteralPath $path) {
                throw "prepare_refuses_existing_artifact:$path"
            }
        }
        if (Test-Path -LiteralPath $paths.Media -PathType Container) {
            $existingMedia = Get-ChildItem -LiteralPath $paths.Media -Force | Select-Object -First 1
            if ($existingMedia) {
                throw "prepare_refuses_nonempty_media_directory:$($paths.Media)"
            }
        }
        $initializeArguments = @(
            "initialize", "--config", $paths.Config, "--run-file", $paths.RunFile,
            "--mode", "vmix", "--source-assumption", "playback_rate=1.0x",
            "--source-assumption", "segment_duration=approximately_60_seconds"
        )
        $resolvedCorpusItem = $CorpusItem
        if (-not $resolvedCorpusItem) {
            $resolvedCorpusItem = "$($paths.Token)-same-stage-turnover"
        }
        $initializeArguments += @("--corpus-item", $resolvedCorpusItem)
        if ($IncludeFilenames) {
            $initializeArguments += "--include-filenames"
        }
        $confirmedBase = @(
            "--config", $paths.Config, "--run-file", $paths.RunFile,
            "--confirm-isolated-validation-database"
        )
        if ($DryRun) {
            Write-Host "DRY RUN paths:"
            $paths | Format-List
            Invoke-ValidationRunner -UvCommand $uvCommand -RunnerPath $runnerPath `
                -RunnerArguments $initializeArguments -Preview
            foreach ($command in @("migrate", "bootstrap", "status")) {
                Invoke-ValidationRunner -UvCommand $uvCommand -RunnerPath $runnerPath `
                    -RunnerArguments (@($command) + $confirmedBase) -Preview
            }
            return
        }
        $psqlCommand = Resolve-PsqlCommand $PsqlPath
        $gitCommand = Resolve-GitCommand
        $databaseProbe = Invoke-DatabaseProbe -Connection $connection -PsqlCommand $psqlCommand
        Enter-RunOperationLock -Paths $paths -Operation $Action
        New-Item -ItemType Directory -Path $ValidationRoot -Force | Out-Null
        New-Item -ItemType Directory -Path $paths.Media -Force | Out-Null
        Write-Utf8NoBom -Path $paths.Config -Content (New-KernelConfiguration $paths)
        Write-EnvironmentManifest -Paths $paths -RepositoryRoot $repositoryRoot `
            -GitCommand $gitCommand `
            -UvCommand $uvCommand -PsqlCommand $psqlCommand -DatabaseProbe $databaseProbe
        Invoke-ValidationRunner -UvCommand $uvCommand -RunnerPath $runnerPath `
            -RunnerArguments $initializeArguments
        foreach ($command in @("migrate", "bootstrap", "status")) {
            Invoke-ValidationRunner -UvCommand $uvCommand -RunnerPath $runnerPath `
                -RunnerArguments (@($command) + $confirmedBase)
        }
        Show-ValidationSummary -State (Read-RunState $paths.RunFile) -Paths $paths
        return
    }

    Enter-RunOperationLock -Paths $paths -Operation $Action

    if ($Action -eq "Initialize") {
        Assert-MatchingConfiguration $paths
        foreach ($path in @($paths.RunFile, $paths.Summary)) {
            if (Test-Path -LiteralPath $path) {
                throw "initialize_refuses_existing_result:$path"
            }
        }
        if (-not (Test-Path -LiteralPath $paths.Media -PathType Container)) {
            throw "validation_media_directory_not_found:$($paths.Media)"
        }
        if (Get-ChildItem -LiteralPath $paths.Media -Force | Select-Object -First 1) {
            throw "initialize_refuses_nonempty_media_directory:$($paths.Media)"
        }
        $resolvedCorpusItem = $CorpusItem
        if (-not $resolvedCorpusItem) {
            $resolvedCorpusItem = "$($paths.Token)-same-stage-turnover"
        }
        $arguments = @(
            "initialize", "--config", $paths.Config, "--run-file", $paths.RunFile,
            "--mode", "vmix", "--source-assumption", "playback_rate=1.0x",
            "--source-assumption", "segment_duration=approximately_60_seconds",
            "--corpus-item", $resolvedCorpusItem
        )
        if ($IncludeFilenames) { $arguments += "--include-filenames" }
        Invoke-ValidationRunner -UvCommand $uvCommand -RunnerPath $runnerPath `
            -RunnerArguments $arguments -Preview:$DryRun
        return
    }

    $null = Assert-MatchingRunArtifacts $paths
    $common = @("--config", $paths.Config, "--run-file", $paths.RunFile)
    $confirmed = $common + "--confirm-isolated-validation-database"
    $arguments = @()

    switch ($Action) {
        "Migrate" { $arguments = @("migrate") + $confirmed }
        "Bootstrap" { $arguments = @("bootstrap") + $confirmed }
        "Expectation" {
            if (-not $ExpectationKey -or -not $Title) {
                throw "expectation_requires_expectation_key_and_title"
            }
            $arguments = @(
                "expectation", "--config", $paths.Config, "--run-file", $paths.RunFile,
                "--confirm-isolated-validation-database", "--key", $ExpectationKey,
                "--title", $Title, "--stage-key", $StageKey
            )
            foreach ($value in $Speaker) { $arguments += @("--speaker", $value) }
            if ($PlannedStart) { $arguments += @("--planned-start", $PlannedStart) }
            if ($PlannedEnd) { $arguments += @("--planned-end", $PlannedEnd) }
        }
        "StartSession" {
            Assert-HumanAuthority
            if ($TurnoverGuard -and $TurnoverPhase -eq "SessionB") {
                $turnoverState = Read-RunState $paths.RunFile
                $null = Assert-TurnoverPredecessorEnded -State $turnoverState
            }
            $arguments = @(
                "start-session", "--config", $paths.Config, "--run-file", $paths.RunFile,
                "--confirm-isolated-validation-database", "--session-label", $SessionLabel,
                "--stage-key", $StageKey, "--at", $script:AuthorityAt
            )
            if ($Title) { $arguments += @("--title", $Title) }
            if ($ExpectationKey) { $arguments += @("--expectation-key", $ExpectationKey) }
        }
        "Cycle" {
            $arguments = @("cycle") + $confirmed + @("--scope", $Scope)
        }
        "DriveCycles" {
            if ($TurnoverGuard) {
                Assert-GuardedDriveAuthority -Paths $paths
            }
            Assert-DriveCyclesWithinInteractiveBudget -Paths $paths
            $arguments = @("drive-cycles") + $confirmed + @(
                "--scope", $Scope,
                "--cycle-every-seconds", ([string]::Format(
                    [System.Globalization.CultureInfo]::InvariantCulture,
                    "{0}",
                    $CycleEverySeconds
                )),
                "--max-cycles", [string]$MaxCycles
            )
        }
        "EndSession" {
            Assert-HumanAuthority
            if (-not $Reason) { throw "end_session_requires_reason" }
            $arguments = @("end-session") + $confirmed + @(
                "--session-label", $SessionLabel, "--at", $script:AuthorityAt,
                "--reason", $Reason
            )
        }
        { $_ -in @("Status", "Checkpoint") } {
            $arguments = @("status") + $confirmed
        }
        "Reconcile" { $arguments = @("reconcile") + $confirmed }
        "AssignAsset" {
            Assert-HumanAuthority
            if (-not $AssetId -or -not $Reason) {
                throw "assign_asset_requires_asset_id_and_reason"
            }
            $arguments = @("assign-asset") + $confirmed + @(
                "--asset-id", $AssetId, "--session-label", $SessionLabel,
                "--reason", $Reason
            )
        }
        "PackageReady" {
            Assert-HumanAuthority
            Invoke-ValidationRunner -UvCommand $uvCommand -RunnerPath $runnerPath `
                -RunnerArguments (@("status") + $confirmed) -Preview:$DryRun
            if (-not $DryRun) { Assert-PackageReadyPreconditions $paths }
            $arguments = @("package-ready") + $confirmed + @("--session-label", $SessionLabel)
        }
        "CompletePackage" {
            Assert-HumanAuthority
            if (-not $Decision -or -not $Reason) {
                throw "complete_package_requires_decision_and_reason"
            }
            $decisionArgument = if ($Decision -eq "Approve") { "--approve" } else { "--reject" }
            $arguments = @("complete-package") + $confirmed + @(
                "--session-label", $SessionLabel, $decisionArgument, "--reason", $Reason
            )
        }
        "RecordStop" {
            if (-not $Reason) { $Reason = "operator_requested_validation_stop" }
            $arguments = @("record-stop") + $common + @("--at", $At, "--reason", $Reason)
        }
        "Reconstruct" { $arguments = @("reconstruct") + $confirmed }
        default { throw "unsupported_controller_action:$Action" }
    }
    Invoke-ValidationRunner -UvCommand $uvCommand -RunnerPath $runnerPath `
        -RunnerArguments $arguments -Preview:$DryRun
    Write-TurnoverBoundaryCheckpoint -Paths $paths
    if (-not $DryRun -and $Action -in @("Status", "Checkpoint", "Reconcile", "PackageReady", "CompletePackage")) {
        Show-ValidationSummary -State (Read-RunState $paths.RunFile) -Paths $paths
    }
}
catch {
    $message = [string]$_.Exception.Message
    if ($message.Contains("://") -or $message -match "(?i)password\s*=") {
        $message = "sensitive diagnostic redacted; inspect the local runner output"
    }
    [Console]::Error.WriteLine("StageFlow validation controller failed: $message")
    exit $script:ControllerExitCode
}
finally {
    Exit-RunOperationLock
}
