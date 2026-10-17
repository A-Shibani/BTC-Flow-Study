param(
    [string]$StartDate = "2026-09-01",
    [string]$EndDate   = "2026-09-30"
)

$ErrorActionPreference = "Stop"

# Always run from the repository root.
Set-Location $PSScriptRoot

# Validate the date format and order before invoking any scripts.
$culture = [System.Globalization.CultureInfo]::InvariantCulture
$start = [datetime]::MinValue
$end = [datetime]::MinValue

$validStart = [datetime]::TryParseExact(
    $StartDate,
    "yyyy-MM-dd",
    $culture,
    [System.Globalization.DateTimeStyles]::None,
    [ref]$start
)

$validEnd = [datetime]::TryParseExact(
    $EndDate,
    "yyyy-MM-dd",
    $culture,
    [System.Globalization.DateTimeStyles]::None,
    [ref]$end
)

if (-not $validStart -or -not $validEnd) {
    throw "Dates must use YYYY-MM-DD format."
}

if ($end -lt $start) {
    throw "--EndDate must be on or after --StartDate."
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Virtual environment Python not found at $python"
}

function Invoke-PythonStep {
    param(
        [string]$StepName,
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "=== $StepName ===" -ForegroundColor Cyan

    & $python @Arguments

    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $StepName (exit code $LASTEXITCODE)"
    }
}

Write-Host "Research period: $StartDate to $EndDate"
Write-Host "Strategy settings remain defined in src\backtest.py."

Invoke-PythonStep `
    -StepName "Download raw archives" `
    -Arguments @(
        "src\download_range.py",
        "--start-date", $StartDate,
        "--end-date", $EndDate
    )

Invoke-PythonStep `
    -StepName "Build one-second dataset and targets" `
    -Arguments @(
        "src\build_multiday_dataset.py",
        "--start-date", $StartDate,
        "--end-date", $EndDate
    )

Invoke-PythonStep `
    -StepName "Run backtest" `
    -Arguments @(
        "src\backtest.py",
        "--start-date", $StartDate,
        "--end-date", $EndDate
    )

Invoke-PythonStep `
    -StepName "Summarise trade results" `
    -Arguments @(
        "src\final_evaluation.py",
        "--start-date", $StartDate,
        "--end-date", $EndDate
    )

Invoke-PythonStep `
    -StepName "Run automated tests" `
    -Arguments @("-m", "pytest", "-q")

Write-Host ""
Write-Host "Pipeline completed successfully." -ForegroundColor Green
Write-Host "Period: $StartDate to $EndDate"