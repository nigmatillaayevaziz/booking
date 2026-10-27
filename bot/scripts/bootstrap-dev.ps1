param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$botRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $botRoot
$target = Join-Path $botRoot ".env"
$legacyEnv = Join-Path $workspaceRoot ".env"

if ((Test-Path -LiteralPath $target) -and -not $Force) {
    throw "bot/.env already exists. Use -Force only if you intentionally want to replace it."
}

function Read-EnvValue([string]$Path, [string]$Name) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return ""
    }
    $prefix = "$Name="
    $line = Get-Content -LiteralPath $Path | Where-Object { $_.StartsWith($prefix) } | Select-Object -First 1
    if (-not $line) {
        return ""
    }
    return $line.Substring($prefix.Length).Trim()
}

function New-RandomBytes([int]$Length) {
    $bytes = [byte[]]::new($Length)
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return $bytes
}

function ConvertTo-Base64Url([byte[]]$Bytes, [switch]$KeepPadding) {
    $value = [Convert]::ToBase64String($Bytes).Replace("+", "-").Replace("/", "_")
    if (-not $KeepPadding) {
        $value = $value.TrimEnd("=")
    }
    return $value
}

$botToken = Read-EnvValue $legacyEnv "BOT_TOKEN"
if (-not $botToken) {
    throw "BOT_TOKEN was not found in the workspace .env file."
}
$adminIds = Read-EnvValue $legacyEnv "ADMIN_IDS"

$webhookSecret = ConvertTo-Base64Url (New-RandomBytes 36)
$appSecret = ConvertTo-Base64Url (New-RandomBytes 48)
$fernetKey = ConvertTo-Base64Url (New-RandomBytes 32) -KeepPadding
$phoneHashKey = ConvertTo-Base64Url (New-RandomBytes 48)

$content = @(
    "ENVIRONMENT=development"
    "BOT_TOKEN=$botToken"
    "TELEGRAM_WEBHOOK_SECRET=$webhookSecret"
    "PUBLIC_BASE_URL=https://bot.example.uz"
    "POSTGRES_DSN=postgresql+asyncpg://booking:booking@postgres:5432/booking"
    "REDIS_URL=redis://redis:6379/0"
    "SUPER_ADMIN_IDS=$adminIds"
    "APP_SECRET=$appSecret"
    "PII_ENCRYPTION_KEY=$fernetKey"
    "PHONE_HASH_KEY=$phoneHashKey"
    "DEFAULT_LANGUAGE=uz"
    "TIMEZONE=Asia/Tashkent"
    "HOLD_MINUTES=15"
    "BOOKING_HORIZON_DAYS=30"
    "BOOKING_CUTOFF_MINUTES=60"
    "MAX_ACTIVE_HOLDS=3"
    "SUPPORT_CONTACT=@support"
    "MANUAL_PAYMENT_ENABLED=true"
    "PAYME_ENABLED=false"
    "CLICK_ENABLED=false"
    "SENTRY_DSN="
    "LOG_LEVEL=INFO"
)

Set-Content -LiteralPath $target -Value $content -Encoding utf8NoBOM
Write-Output "Created bot/.env with generated local secrets."
