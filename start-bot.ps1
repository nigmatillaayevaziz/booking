$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$nodePath = "C:\Program Files\nodejs\node.exe"

if (-not (Test-Path -LiteralPath $nodePath)) {
    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    if (-not $nodeCommand) {
        throw "Node.js 22.5+ topilmadi. https://nodejs.org saytidan LTS versiyani o'rnating."
    }
    $nodePath = $nodeCommand.Source
}

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot ".env"))) {
    Copy-Item -LiteralPath (Join-Path $projectRoot ".env.example") -Destination (Join-Path $projectRoot ".env")
    throw ".env yaratildi. BOT_TOKEN qiymatini yozing va start-bot.ps1 ni qayta ishga tushiring."
}

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot "node_modules\mongodb\package.json"))) {
    $npmPath = Join-Path (Split-Path -Parent $nodePath) "npm.cmd"
    if (-not (Test-Path -LiteralPath $npmPath)) { throw "npm.cmd topilmadi." }
    Write-Output "MongoDB drayveri o'rnatilmoqda..."
    & $npmPath install --omit=dev --prefix $projectRoot
    if ($LASTEXITCODE -ne 0) { throw "npm install bajarilmadi." }
}

$envContent = Get-Content -Raw -LiteralPath (Join-Path $projectRoot ".env")
if ($envContent -match "BOT_TOKEN\s*=\s*(replace_with_new_token|\s*$)") {
    throw ".env ichidagi BOT_TOKEN qiymatini BotFather bergan token bilan almashtiring."
}

$dataDirectory = Join-Path $projectRoot "data"
$logDirectory = Join-Path $projectRoot "logs"
$pidFile = Join-Path $dataDirectory "bot.pid"
New-Item -ItemType Directory -Force -Path $dataDirectory, $logDirectory | Out-Null

if (Test-Path -LiteralPath $pidFile) {
    $oldPid = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
        Write-Output "Bot allaqachon ishlayapti. PID: $oldPid"
        exit 0
    }
    Remove-Item -LiteralPath $pidFile -Force
}

$process = Start-Process -FilePath $nodePath `
    -ArgumentList "src/main.mjs" `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDirectory "bot.log") `
    -RedirectStandardError (Join-Path $logDirectory "bot-error.log") `
    -PassThru

Start-Sleep -Seconds 3
if ($process.HasExited) {
    Write-Output "Bot ishga tushmadi. Xato:"
    Get-Content -LiteralPath (Join-Path $logDirectory "bot-error.log") -Tail 30
    exit 1
}

Write-Output "Bot ishga tushdi. PID: $($process.Id)"
Write-Output "Loglar: $logDirectory"

