$ErrorActionPreference = "Stop"
$pidFile = Join-Path $PSScriptRoot "data\bot.pid"
if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Output "Bot ishlamayapti (PID fayli yo'q)."
    exit 0
}

$botPid = Get-Content -LiteralPath $pidFile
$process = Get-Process -Id $botPid -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $botPid
    Write-Output "Bot to'xtatildi. PID: $botPid"
} else {
    Write-Output "Bot jarayoni topilmadi."
}
Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue

