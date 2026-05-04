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
    & docker compose @ComposeFiles down
    if ($LASTEXITCODE -ne 0) {
        throw "Docker compose stop failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
