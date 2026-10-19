$src = Join-Path $PSScriptRoot '..\mql5\BridgeEA.mq5'
if (-not (Test-Path $src)) { Write-Host "BridgeEA.mq5 topilmadi: $src"; exit 1 }

$root = Join-Path $env:APPDATA 'MetaQuotes\Terminal'
$found = $false
foreach ($dir in Get-ChildItem $root -Directory -ErrorAction SilentlyContinue) {
    $originFile = Join-Path $dir.FullName 'origin.txt'
    if (-not (Test-Path $originFile)) { continue }
    $origin = (Get-Content $originFile -Encoding Unicode).Trim()
    if ($origin -notmatch 'XM') { continue }
    $editor = Join-Path $origin 'MetaEditor64.exe'
    if (-not (Test-Path $editor)) { continue }

    $experts = Join-Path $dir.FullName 'MQL5\Experts'
    New-Item -ItemType Directory -Force $experts | Out-Null
    Copy-Item $src (Join-Path $experts 'BridgeEA.mq5') -Force
    $log = Join-Path $experts 'compile.log'
    Start-Process -FilePath $editor -ArgumentList "/compile:`"$experts\BridgeEA.mq5`"", "/log:`"$log`"" -Wait
    Write-Host "MT5: $origin"
    Get-Content $log -Encoding Unicode | Select-String 'Result|error'
    $found = $true
}
if (-not $found) { Write-Host "XM MT5 topilmadi. Avval XM MT5 ni o'rnating va bir marta oching." }
