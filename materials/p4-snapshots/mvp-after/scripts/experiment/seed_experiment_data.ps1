param(
    [int]$Products = 40,
    [int]$Carts = 8
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$SutDir = Join-Path $RepoRoot "sut\habaneras-de-lino-drf-api"
$ComposeFiles = @(
    "-f", "docker-compose.yml",
    "-f", "docker-compose.experiment.yml",
    "-f", "docker-compose.chaos.yml"
)

Push-Location $SutDir
try {
    & docker compose @ComposeFiles exec -T api python manage.py seed_experiment_data --products $Products --carts $Carts
    if ($LASTEXITCODE -ne 0) {
        throw "Experiment data seed failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
