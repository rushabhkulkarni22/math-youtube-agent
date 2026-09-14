param([switch]$Install)

$ErrorActionPreference = "Stop"
$TaskName = "Math YouTube Agent - Hourly Local Upload"
$ProjectRoot = $PSScriptRoot
$ScriptPath = $MyInvocation.MyCommand.Path
$LogDirectory = Join-Path $ProjectRoot "logs"
$LogPath = Join-Path $LogDirectory "hourly-local-upload.log"
$LockPath = Join-Path $LogDirectory "hourly-local-upload.lock"

if ($Install) {
    $firstRun = (Get-Date).AddMinutes(1)
    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`"" `
        -WorkingDirectory $ProjectRoot
    $trigger = New-ScheduledTaskTrigger `
        -Once -At $firstRun `
        -RepetitionInterval (New-TimeSpan -Hours 1)
    $settings = New-ScheduledTaskSettingsSet `
        -WakeToRun `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 55) `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 5)
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Generate and upload one private math video locally every hour." `
        -Force | Out-Null
    Write-Host "Installed '$TaskName'. First automatic run: $firstRun"
    exit 0
}

New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
$lockStream = $null
try {
    $lockStream = [System.IO.File]::Open(
        $LockPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
} catch [System.IO.IOException] {
    Add-Content $LogPath "$(Get-Date -Format s) SKIPPED: Another local upload is active."
    exit 0
}

try {
    Add-Content $LogPath "$(Get-Date -Format s) STARTED"
    $projectEnv = Join-Path $ProjectRoot ".env"
    $fallbackEnv = Join-Path (Split-Path $ProjectRoot -Parent) "RAG\.env"
    $envPath = if (Test-Path -LiteralPath $projectEnv) { $projectEnv } else { $fallbackEnv }
    $keyLine = Get-Content -LiteralPath $envPath |
        Where-Object { $_ -match '^\s*GROQ_API_KEY\s*=' } |
        Select-Object -First 1
    if (-not $keyLine) { throw "GROQ_API_KEY was not found in $envPath" }

    $env:GROQ_API_KEY = ($keyLine -split '=', 2)[1].Trim().Trim('"').Trim("'")
    $env:DRY_RUN = "false"
    $env:YOUTUBE_PRIVACY = "private"
    $env:MANIM_QUALITY = "low_quality"
    $uv = (Get-Command uv -ErrorAction Stop).Source

    Push-Location $ProjectRoot
    try {
        & $uv run python main.py --limit 1 --max-prompt-attempts 3 --fail-on-item-error *>> $LogPath
        if ($LASTEXITCODE -ne 0) { throw "Video pipeline exited with code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
    Add-Content $LogPath "$(Get-Date -Format s) SUCCEEDED"
    exit 0
} catch {
    Add-Content $LogPath "$(Get-Date -Format s) FAILED: $($_.Exception.Message)"
    exit 1
} finally {
    if ($lockStream) { $lockStream.Dispose() }
    Remove-Item -LiteralPath $LockPath -Force -ErrorAction SilentlyContinue
}
