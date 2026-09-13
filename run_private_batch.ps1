$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$projectEnv = Join-Path $projectRoot ".env"
$fallbackEnv = Join-Path (Split-Path $projectRoot -Parent) "RAG\.env"
$envPath = if (Test-Path -LiteralPath $projectEnv) { $projectEnv } else { $fallbackEnv }

$keyLine = Get-Content -LiteralPath $envPath |
    Where-Object { $_ -match '^\s*GROQ_API_KEY\s*=' } |
    Select-Object -First 1
if (-not $keyLine) {
    throw "GROQ_API_KEY was not found in $envPath"
}

$env:GROQ_API_KEY = ($keyLine -split '=', 2)[1].Trim().Trim('"').Trim("'")
$env:DRY_RUN = "false"
$env:YOUTUBE_PRIVACY = "private"

Set-Location -LiteralPath $projectRoot
uv run python main.py --limit 1
