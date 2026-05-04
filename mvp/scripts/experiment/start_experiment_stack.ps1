param(
    [switch]$Build
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
    $args = @($ComposeFiles + @("up", "-d"))
    if ($Build) {
        $args += "--build"
    }
    & docker compose @args
    if ($LASTEXITCODE -ne 0) {
        throw "Docker compose start failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
