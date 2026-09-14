param(
    [switch]$Install,
    [switch]$RunSoon,
    [ValidateRange(5, 1440)][int]$CheckIntervalMinutes = 5
)

$ErrorActionPreference = "Stop"
$TaskName = "Math YouTube Agent - Hourly Cloud Upload"
$Repository = "rushabhkulkarni22/math-youtube-agent"
$Workflow = "hourly-video.yml"
$ScriptPath = $MyInvocation.MyCommand.Path
$LogPath = Join-Path $PSScriptRoot "logs\hourly-trigger.log"
$ForceMarker = Join-Path $PSScriptRoot "logs\force-next-trigger.marker"

if ($Install) {
    $nextHour = if ($RunSoon) { (Get-Date).AddMinutes(1) } else {
        (Get-Date).Date.AddHours((Get-Date).Hour + 1)
    }
    if ($RunSoon) {
        New-Item -ItemType File -Path $ForceMarker -Force | Out-Null
    }
    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
        -WorkingDirectory $PSScriptRoot
    $trigger = New-ScheduledTaskTrigger `
        -Once -At $nextHour `
        -RepetitionInterval (New-TimeSpan -Minutes $CheckIntervalMinutes)
    $settings = New-ScheduledTaskSettingsSet `
        -WakeToRun `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Dispatch one private mathematical YouTube video cloud job every hour." `
        -Force | Out-Null
    Write-Host "Installed '$TaskName'. First trigger: $nextHour; check interval: $CheckIntervalMinutes minutes"
    exit 0
}

$logDirectory = Split-Path $LogPath
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$ghCandidates = @(
    "C:\Program Files\GitHub CLI\gh.exe",
    "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe"
)
$gh = $ghCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $gh) {
    $command = Get-Command gh -ErrorAction SilentlyContinue
    if ($command) { $gh = $command.Source }
}
if (-not $gh) {
    Add-Content $LogPath "$timestamp ERROR: GitHub CLI was not found."
    exit 1
}

$runsJson = & $gh run list `
    --repo $Repository `
    --workflow $Workflow `
    --limit 10 `
    --json status,conclusion,updatedAt
if ($LASTEXITCODE -ne 0) {
    Add-Content $LogPath "$timestamp ERROR: Unable to query GitHub workflow status."
    exit $LASTEXITCODE
}
$runs = $runsJson | ConvertFrom-Json
$activeRuns = @($runs | Where-Object { $_.status -in @("queued", "in_progress") }).Count
if ($activeRuns -gt 0) {
    Add-Content $LogPath "$timestamp SKIPPED: A cloud workflow is already active."
    exit 0
}

$forceThisRun = Test-Path $ForceMarker
if ($forceThisRun) {
    Remove-Item -LiteralPath $ForceMarker -Force
}
$latestGreen = $runs |
    Where-Object { $_.status -eq "completed" -and $_.conclusion -eq "success" } |
    Sort-Object { [datetime]$_.updatedAt } -Descending |
    Select-Object -First 1
if ($latestGreen -and -not $forceThisRun) {
    $greenAge = (Get-Date).ToUniversalTime() - ([datetime]$latestGreen.updatedAt).ToUniversalTime()
    if ($greenAge.TotalMinutes -lt 60) {
        $remaining = [math]::Ceiling(60 - $greenAge.TotalMinutes)
        Add-Content $LogPath "$timestamp SKIPPED: Last green workflow was less than one hour ago ($remaining minutes remaining)."
        exit 0
    }
}

& $gh workflow run $Workflow --repo $Repository
if ($LASTEXITCODE -eq 0) {
    Add-Content $LogPath "$timestamp DISPATCHED: Hourly cloud workflow started."
} else {
    Add-Content $LogPath "$timestamp ERROR: GitHub workflow dispatch failed."
}
exit $LASTEXITCODE
