# CyberWatch Auto-Build Watcher
# Usage: .\watch-and-build.ps1

$ROOT   = $PSScriptRoot
$SRC    = Join-Path $ROOT "src"
$CONFIG = Join-Path $ROOT "config"
$EXE    = Join-Path $ROOT "dist\CyberWatch\CyberWatch.exe"
$SPEC   = Join-Path $ROOT "cyberwatch.spec"
$script:debounce   = [DateTime]::MinValue
$script:debounceMs = 3000

function Kill-CW {
    foreach ($p in (Get-Process -Name "CyberWatch" -EA SilentlyContinue)) {
        Write-Host ("[STOP] PID " + $p.Id) -ForegroundColor Yellow
        $p.Kill()
    }
    Start-Sleep -Seconds 1
}

function Build-And-Launch {
    $t = Get-Date
    Write-Host "[BUILD] Rebuild en cours..." -ForegroundColor Cyan
    Kill-CW
    Set-Location $ROOT
    & pyinstaller $SPEC | Out-Null
    $sec = [math]::Round(((Get-Date)-$t).TotalSeconds,1)
    if ($LASTEXITCODE -eq 0) {
        Write-Host ("[OK] " + $sec + "s") -ForegroundColor Green
        Start-Sleep -Seconds 1
        Start-Process $EXE
        Write-Host "[LAUNCH] CyberWatch relance!" -ForegroundColor Green
    } else {
        Write-Host "[ERREUR] Build echoue" -ForegroundColor Red
    }
    Write-Host "En attente..." -ForegroundColor DarkGray
}

$w1 = New-Object System.IO.FileSystemWatcher
$w1.Path = $SRC
$w1.Filter = "*.py"
$w1.IncludeSubdirectories = $true
$w1.NotifyFilter = [IO.NotifyFilters]::LastWrite
$w2 = New-Object System.IO.FileSystemWatcher
$w2.Path = $CONFIG
$w2.Filter = "*.yaml"
$w2.IncludeSubdirectories = $false
$w2.NotifyFilter = [IO.NotifyFilters]::LastWrite

$action = {
    $now = [DateTime]::Now
    if (($now - $script:debounce).TotalMilliseconds -gt $script:debounceMs) {
        $script:debounce = $now
        Write-Host ("[CHANGE] " + $Event.SourceEventArgs.FullPath) -ForegroundColor Magenta
        Start-Sleep -Seconds 2
        Build-And-Launch
    }
}

Register-ObjectEvent $w1 "Changed" -Action $action | Out-Null
Register-ObjectEvent $w1 "Created" -Action $action | Out-Null
Register-ObjectEvent $w2 "Changed" -Action $action | Out-Null
$w1.EnableRaisingEvents = $true
$w2.EnableRaisingEvents = $true

Write-Host "=== CyberWatch Watcher ACTIF ===" -ForegroundColor Cyan
Write-Host "src/*.py ou config/*.yaml -> rebuild + relance auto" -ForegroundColor Green
Write-Host "Ctrl+C pour arreter" -ForegroundColor DarkGray

if (-not (Get-Process -Name "CyberWatch" -EA SilentlyContinue)) {
    Start-Process $EXE
}

try { while ($true) { Start-Sleep -Seconds 1 } }
finally { $w1.Dispose(); $w2.Dispose(); Write-Host "Watcher arrete." }
