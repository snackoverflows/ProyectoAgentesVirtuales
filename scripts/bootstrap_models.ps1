param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string[]]$OllamaModels = @("gemma3"),
    [string]$WhisperModel = "base",
    [string]$MoonshineLanguage = "es",
    [switch]$SkipOllamaPull,
    [switch]$SkipWhisperPreload,
    [switch]$SkipMoonshinePreload
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
$pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "No se encontro backend\.venv\Scripts\python.exe. Ejecuta primero scripts\bootstrap_local.ps1."
}

Write-Step "Precargando modelos de Whisper"
if (-not $SkipWhisperPreload) {
    & $pythonExe -c "import whisper; whisper.load_model('$WhisperModel'); print('whisper_model_ok')"
}
else {
    Write-Host "Se omitio la precarga de Whisper." -ForegroundColor Yellow
}

Write-Step "Precargando modelos de Moonshine"
if (-not $SkipMoonshinePreload) {
    & $pythonExe -c "from moonshine_voice.download import get_model_for_language; path, arch = get_model_for_language('$MoonshineLanguage'); print(f'moonshine_model_ok:{path}:{arch.name}')"
}
else {
    Write-Host "Se omitio la precarga de Moonshine." -ForegroundColor Yellow
}

Write-Step "Descargando modelos de Ollama"
if (-not $SkipOllamaPull) {
    $ollamaPath = Test-CommandAvailable "ollama"
    if ($null -eq $ollamaPath) {
        Write-Host "Ollama no esta instalado. Instala Ollama y vuelve a ejecutar este script." -ForegroundColor Yellow
    }
    else {
        foreach ($modelName in $OllamaModels) {
            Write-Host "Descargando modelo Ollama: $modelName" -ForegroundColor Green
            & $ollamaPath pull $modelName
        }
    }
}
else {
    Write-Host "Se omitio la descarga de Ollama." -ForegroundColor Yellow
}

Write-Step "Checklist de runtimes externos pendientes"
$checks = @(
    @{ Name = "Piper"; Binary = "piper"; Env = "PIPER_BINARY, PIPER_MODEL_PATH, PIPER_CONFIG_PATH" },
    @{ Name = "Kokoro"; Binary = $null; Env = "KOKORO_MODEL_PATH, KOKORO_VOICE" }
)

foreach ($check in $checks) {
    $binaryPath = $null
    if ($null -ne $check.Binary) {
        $binaryPath = Test-CommandAvailable $check.Binary
    }
    if ($null -ne $binaryPath) {
        Write-Host ("{0}: listo en {1}" -f $check.Name, $binaryPath) -ForegroundColor Green
    }
    else {
        Write-Host ("{0}: pendiente. Configura {1}" -f $check.Name, $check.Env) -ForegroundColor Yellow
    }
}

Write-Step "Bootstrap de modelos completado"
Write-Host "Revisa backend\config.env para apuntar a los modelos locales descargados." -ForegroundColor Cyan
