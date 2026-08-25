[CmdletBinding()]
param(
    [switch]$Check,
    [string]$EnvFile = '.env.production'
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'

if (Test-Path -LiteralPath $venvPython) {
    $pythonCommand = $venvPython
} else {
    $pythonOnPath = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonOnPath) {
        Write-Error 'Python was not found. Install Python 3.11+ first.'
        exit 1
    }
    $pythonCommand = $pythonOnPath.Source
}

$launcherArguments = @('-m', 'scripts.deploy', '--env-file', $EnvFile)
if ($Check) {
    $launcherArguments += '--check'
}

Push-Location $repoRoot
try {
    & $pythonCommand @launcherArguments
    $launcherExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

exit $launcherExitCode
