# One-step launcher for the ATS dashboard (Windows).
# Installs what is missing, signs you in to Databricks with YOUR account, then opens the dashboard.
# Double-click Start-Dashboard.bat; it runs this file.
param([int]$Port = 8051)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# Workspace settings for the IS4030 project. These are identifiers, not credentials.
$WorkspaceHost = 'https://dbc-4dc963bf-e25b.cloud.databricks.com'
$Profile_      = 'IS4030'
$env:DATABRICKS_CONFIG_PROFILE = $Profile_
$env:DATABRICKS_WAREHOUSE_ID   = 'b5fcad890d7d8f13'
$env:ATS_RUNNER_JOB_ID         = '753433383365592'

function Write-Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function Stop-WithMessage($text) { Write-Host "`n$text" -ForegroundColor Red; Read-Host 'Press Enter to close'; exit 1 }
function Test-Command($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Update-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Install-WithWinget($id, $label) {
    if (-not (Test-Command winget)) { Stop-WithMessage "$label is not installed and winget is not available. Install $label yourself, then run this again." }
    $answer = Read-Host "$label is not installed. Install it now with winget? (y/n)"
    if ($answer -notmatch '^[Yy]') { Stop-WithMessage "$label is required. Nothing was installed." }
    winget install --id $id -e --accept-source-agreements --accept-package-agreements
    Update-Path
}

Write-Step 'Checking Python'
# The Microsoft Store placeholder named python.exe is not a real Python, so test by running it.
function Find-Python {
    foreach ($candidate in @(@('py', '-3'), @('python'))) {
        $exe = $candidate[0]
        if (Test-Command $exe) {
            $rest = @($candidate | Select-Object -Skip 1)
            try { & $exe @rest -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>$null; if ($LASTEXITCODE -eq 0) { return ,$candidate } } catch {}
        }
    }
    return $null
}
$python = Find-Python
if (-not $python) { Install-WithWinget 'Python.Python.3.12' 'Python 3.12'; $python = Find-Python }
if (-not $python) { Stop-WithMessage 'Python was installed but this window cannot see it yet. Close this window and run Start-Dashboard.bat again.' }

Write-Step 'Setting up the dashboard packages (first run takes a few minutes)'
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    $exe = $python[0]; $rest = @($python | Select-Object -Skip 1)
    & $exe @rest -m venv .venv
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage 'Could not create the Python environment.' }
}
& $venvPython -m pip install --quiet --disable-pip-version-check -r web_dashboard\requirements.txt
if ($LASTEXITCODE -ne 0) { Stop-WithMessage 'Could not install the dashboard packages. Check your internet connection and run this again.' }

Write-Step 'Checking the Databricks command-line tool'
if (-not (Test-Command databricks)) { Install-WithWinget 'Databricks.DatabricksCLI' 'The Databricks CLI' }
if (-not (Test-Command databricks)) { Stop-WithMessage 'The Databricks CLI was installed but this window cannot see it yet. Close this window and run Start-Dashboard.bat again.' }

Write-Step 'Signing in to Databricks'
# Each person signs in with their own account. No password or token is stored in this project.
$ErrorActionPreference = 'Continue'
databricks auth token --profile $Profile_ *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'A browser window will open. Sign in with your own Databricks account, then come back here.'
    databricks auth login --host $WorkspaceHost --profile $Profile_
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage 'Databricks sign-in did not finish. Run this again to retry.' }
} else {
    Write-Host 'Already signed in.'
}
$ErrorActionPreference = 'Stop'

Write-Step "Starting the dashboard at http://127.0.0.1:$Port"
$server = Start-Process -FilePath $venvPython -ArgumentList 'web_dashboard\server.py', '--live', '--port', $Port -NoNewWindow -PassThru
$ready = $false
foreach ($i in 1..60) {
    Start-Sleep -Seconds 1
    if ($server.HasExited) { break }
    try { Invoke-WebRequest "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 2 | Out-Null; $ready = $true; break } catch {}
}
if (-not $ready) { Stop-WithMessage "The dashboard did not start. If port $Port is already in use, close the other dashboard window and try again." }
Start-Process "http://127.0.0.1:$Port/"
Write-Host "`nThe dashboard is open in your browser. Keep this window open while you use it." -ForegroundColor Green
Write-Host 'Close this window to stop the dashboard.'
try { Wait-Process -Id $server.Id } finally { if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force } }
