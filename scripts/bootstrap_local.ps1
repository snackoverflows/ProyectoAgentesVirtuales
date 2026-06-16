param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [switch]$SkipPipInstall,
    [switch]$ForceConfigCopy
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Test-CommandAvailable {
    param([string]$CommandName)
    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        return $null
    }
    return $command.Source
}

$backendDir = Join-Path $ProjectRoot "backend"
$venvDir = Join-Path $backendDir ".venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
$configExample = Join-Path $backendDir "config.env.example"
$configPath = Join-Path $backendDir "config.env"

Write-Step "Validando estructura del proyecto"
if (-not (Test-Path $backendDir)) {
    throw "No se encontro la carpeta backend en: $backendDir"
}

Write-Step "Asegurando entorno virtual"
if (-not (Test-Path $pythonExe)) {
    $pyLauncher = Test-CommandAvailable "py"
    if ($null -eq $pyLauncher) {
        throw "No se encontro 'py'. Instala Python o crea backend\.venv manualmente."
    }
    & $pyLauncher -3 -m venv $venvDir
}

Write-Step "Mostrando version de Python"
& $pythonExe --version

Write-Step "Asegurando config.env"
if (-not (Test-Path $configPath) -or $ForceConfigCopy) {
    Copy-Item $configExample $configPath -Force
    Write-Host "config.env creado desde config.env.example" -ForegroundColor Yellow
}
else {
    Write-Host "config.env ya existe; no se sobrescribe." -ForegroundColor Green
}

Write-Step "Creando carpetas locales de modelos"
$modelDirs = @(
    "backend\models",
    "backend\models\piper",
    "backend\models\moonshine",
    "backend\models\kokoro",
    "backend\models\downloads"
)
foreach ($relativeDir in $modelDirs) {
    $targetDir = Join-Path $ProjectRoot $relativeDir
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
}

Write-Step "Instalando dependencias Python"
if (-not $SkipPipInstall) {
    Push-Location $backendDir
    try {
        & $pythonExe -m pip install -e .[all]
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "Se omitio la instalacion de pip por solicitud." -ForegroundColor Yellow
}

Write-Step "Detectando runtimes locales"
$runtimeChecks = [ordered]@{
    "ollama" = (Test-CommandAvailable "ollama")
    "ffmpeg" = (Test-CommandAvailable "ffmpeg")
    "piper" = (Test-CommandAvailable "piper")
}

foreach ($entry in $runtimeChecks.GetEnumerator()) {
    if ($null -ne $entry.Value) {
        Write-Host ("{0}: {1}" -f $entry.Key, $entry.Value) -ForegroundColor Green
    }
    else {
        Write-Host ("{0}: no encontrado" -f $entry.Key) -ForegroundColor Yellow
    }
}

Write-Step "Notas de compatibilidad"
$pythonVersion = & $pythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$pythonVersion -ge [version]"3.13") {
    Write-Host "Python 3.13 detectado: Kokoro puede requerir un entorno 3.10/3.11 aparte." -ForegroundColor Yellow
}
else {
    Write-Host "La version de Python es apta para intentar Kokoro." -ForegroundColor Green
}

Write-Step "Bootstrap local completado"
Write-Host "Siguiente paso sugerido: scripts\bootstrap_models.ps1" -ForegroundColor Cyan
