param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("testnet", "production")]
    [string]$Profile
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $root ".env.$Profile"
$target = Join-Path $root ".env"

if (-not (Test-Path $source)) {
    Write-Error "No existe el perfil: $source"
    exit 1
}

Copy-Item -Path $source -Destination $target -Force
Write-Host "✅ Perfil aplicado: $Profile"
Write-Host "📄 Archivo activo: $target"

if ($Profile -eq "production") {
    Write-Host "⚠️ Revisa BINANCE_API_KEY/BINANCE_API_SECRET y AUTO_TRADE_ENABLED antes de operar." -ForegroundColor Yellow
}
