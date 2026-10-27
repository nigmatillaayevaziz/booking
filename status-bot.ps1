$pidFile = Join-Path $PSScriptRoot "data\bot.pid"
if (Test-Path -LiteralPath $pidFile) {
    $botPid = Get-Content -LiteralPath $pidFile
    $process = Get-Process -Id $botPid -ErrorAction SilentlyContinue
    if ($process) {
        Write-Output "Bot ishlayapti. PID: $botPid"
        exit 0
    }
}
Write-Output "Bot ishlamayapti."
exit 1

