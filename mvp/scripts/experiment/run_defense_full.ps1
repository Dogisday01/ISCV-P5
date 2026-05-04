param(
    [ValidateSet("Full", "Demo")]
    [string]$Mode = "Full",
    [switch]$SkipMutation,
    [switch]$KeepStack
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$SutDir = Join-Path $RepoRoot "sut\habaneras-de-lino-drf-api"
$ArtifactsDir = Join-Path $RepoRoot "artifacts"
$UnitDir = Join-Path $ArtifactsDir "unit"
$IntegrationDir = Join-Path $ArtifactsDir "integration"
$PerformanceDir = Join-Path $ArtifactsDir "performance"
$MutationDir = Join-Path $ArtifactsDir "mutation"
$ChaosDir = Join-Path $ArtifactsDir "chaos"
$BaseUrl = "http://host.docker.internal:8002/api"
$HealthUrl = "http://localhost:8002/api/categories/"
$ComposeFiles = @(
    "-f", "docker-compose.yml",
    "-f", "docker-compose.experiment.yml",
    "-f", "docker-compose.chaos.yml"
)

function New-Dir([string]$Path) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Resolve-Python {
    if ($env:ASSIGNMENT3_PYTHON -and (Test-Path $env:ASSIGNMENT3_PYTHON)) {
        return $env:ASSIGNMENT3_PYTHON
    }
    $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\python-3.12.12-windows-x86_64\python.exe"
    if (Test-Path $bundled) {
        return $bundled
    }
    return "python"
}

function Invoke-Checked([string]$Name, [scriptblock]$Command) {
    Write-Host ""
    Write-Host "==> $Name"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Wait-Api {
    Write-Host "Waiting for API health endpoint..."
    for ($i = 1; $i -le 60; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                Write-Host "API is ready."
                return
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "API did not become ready at $HealthUrl"
}

function Invoke-Compose([string[]]$Args) {
    Push-Location $SutDir
    try {
        & docker compose @ComposeFiles @Args
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose $($Args -join ' ') failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-K6Scenario([string]$Scenario, [hashtable]$Environment) {
    $summaryPath = "/artifacts/$Scenario-summary.json"
    $envArgs = @("-e", "BASE_URL=$BaseUrl", "-e", "SCENARIO=$Scenario")
    foreach ($entry in $Environment.GetEnumerator()) {
        $envArgs += @("-e", "$($entry.Key)=$($entry.Value)")
    }
    & docker run --rm --network host @envArgs -v "${PerformanceDir}:/artifacts" -v "${RepoRoot}:/work:ro" grafana/k6:0.49.0 run --summary-export $summaryPath /work/tests/performance/assignment3_scenarios.js
    if ($LASTEXITCODE -ne 0) {
        throw "k6 $Scenario scenario failed with exit code $LASTEXITCODE"
    }
}

New-Dir $UnitDir
New-Dir $IntegrationDir
New-Dir $PerformanceDir
New-Dir $MutationDir
New-Dir $ChaosDir

$Python = Resolve-Python
$commonPytestEnv = @{
    PYTHONPATH = Join-Path $RepoRoot "sut\habaneras-de-lino-drf-api"
    DJANGO_SETTINGS_MODULE = "config.settings.local"
}

try {
    Invoke-Checked "Start experiment Docker stack" { Invoke-Compose @("up", "-d", "--build") }
    Wait-Api

    Invoke-Checked "Seed experiment data" {
        Push-Location $SutDir
        try {
            & docker compose @ComposeFiles exec -T api python manage.py seed_experiment_data --products 40 --carts 8
        }
        finally {
            Pop-Location
        }
    }

    Invoke-Checked "Run unit tests" {
        Push-Location $RepoRoot
        try {
            $env:PYTHONPATH = $commonPytestEnv.PYTHONPATH
            $env:DJANGO_SETTINGS_MODULE = $commonPytestEnv.DJANGO_SETTINGS_MODULE
            & $Python -m pytest tests/unit/ -q --tb=short *> (Join-Path $UnitDir "unit-results.txt")
        }
        finally {
            Pop-Location
        }
    }

    Invoke-Checked "Run integration smoke tests" {
        Push-Location $RepoRoot
        try {
            $env:PYTHONPATH = $commonPytestEnv.PYTHONPATH
            $env:DJANGO_SETTINGS_MODULE = $commonPytestEnv.DJANGO_SETTINGS_MODULE
            & $Python -m pytest tests/integration/test_api_endpoints.py tests/integration/test_response_times.py -q --tb=short *> (Join-Path $IntegrationDir "integration-smoke-results.txt")
        }
        finally {
            Pop-Location
        }
    }

    Write-Host ""
    Write-Host "==> Run performance scenarios"
    if ($Mode -eq "Demo") {
        Invoke-K6Scenario "normal" @{ NORMAL_VUS = "1"; NORMAL_DURATION = "15s" }
        Invoke-K6Scenario "load" @{ LOAD_VUS = "3"; LOAD_RAMP_UP = "10s"; LOAD_DURATION = "20s"; LOAD_RAMP_DOWN = "5s" }
        Invoke-K6Scenario "peak" @{ PEAK_VUS = "5"; PEAK_RAMP_UP = "10s"; PEAK_HOLD = "15s"; PEAK_RAMP_DOWN = "5s" }
        Invoke-K6Scenario "endurance" @{ ENDURANCE_VUS = "2"; ENDURANCE_DURATION = "45s" }
    }
    else {
        Invoke-K6Scenario "normal" @{}
        Invoke-K6Scenario "load" @{}
        Invoke-K6Scenario "peak" @{}
        Invoke-K6Scenario "endurance" @{}
    }

    if (-not $SkipMutation) {
        Invoke-Checked "Run mutation testing in isolated Linux container" {
            $bash = @"
set -euo pipefail
apt-get update >/dev/null
apt-get install -y --no-install-recommends gcc g++ libpq-dev rsync >/dev/null
python -m pip install --upgrade pip >/dev/null
mkdir -p /tmp/work
rsync -a --delete --exclude .git --exclude artifacts --exclude .mutmut-cache /src/ /tmp/work/
cd /tmp/work
python -m pip install -r requirements.txt -r requirements-experiment.txt >/dev/null
python scripts/experiment/run_mutation.py --output-dir /out
"@
            & docker run --rm -v "${RepoRoot}:/src:ro" -v "${MutationDir}:/out" python:3.9-slim-bullseye bash -lc $bash
        }
    }

    Invoke-Checked "Run chaos tests" {
        Push-Location $RepoRoot
        try {
            & $Python scripts/experiment/run_chaos.py --base-url $BaseUrl --toxiproxy-url http://localhost:8474 --probes 20 --output-dir $ChaosDir
        }
        finally {
            Pop-Location
        }
    }

    Invoke-Checked "Build consolidated summary" {
        Push-Location $RepoRoot
        try {
            & $Python scripts/experiment/build_summary.py --output (Join-Path $ArtifactsDir "summary.md")
        }
        finally {
            Pop-Location
        }
    }

    Write-Host ""
    Write-Host "Defense run completed. Summary: $(Join-Path $ArtifactsDir 'summary.md')"
}
finally {
    if (-not $KeepStack) {
        Write-Host ""
        Write-Host "Stopping experiment Docker stack..."
        try {
            Invoke-Compose @("down")
        }
        catch {
            Write-Warning $_
        }
    }
}
