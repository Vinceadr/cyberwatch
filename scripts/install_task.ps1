# CyberWatch - Windows Task Scheduler Automation
$ErrorActionPreference = "Stop"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$PythonExe  = (Get-Command python -ErrorAction SilentlyContinue).Source
$ExePath = Join-Path $ProjectDir "dist\CyberWatch\CyberWatch.exe"
$UseExe  = Test-Path $ExePath
if ($UseExe) {
    $ActionFetch = New-ScheduledTaskAction -Execute $ExePath -Argument "--pipeline"
    $ActionPurge = New-ScheduledTaskAction -Execute $ExePath -Argument "--purge"
} else {
    if (-not $PythonExe) { throw "Python introuvable dans PATH." }
    $FetchScript = Join-Path $ScriptDir "run_pipeline.py"
    $PurgeScript = Join-Path $ScriptDir "purge_pipeline.py"
    $ActionFetch = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$FetchScript`"" -WorkingDirectory $ProjectDir
    $ActionPurge = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$PurgeScript`"" -WorkingDirectory $ProjectDir
}
$Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Limited -LogonType Interactive

# Task 1: fetch every 30 min
try { Unregister-ScheduledTask -TaskPath "\CyberWatch\" -TaskName "CyberWatch-Fetch" -Confirm:$false -ErrorAction SilentlyContinue } catch {}
try { Unregister-ScheduledTask -TaskPath "\CyberWatch\" -TaskName "CyberWatch-Fetch30" -Confirm:$false -ErrorAction SilentlyContinue } catch {}
schtasks /create /tn "\CyberWatch\CyberWatch-Fetch" /sc ONLOGON /ru "$env:USERDOMAIN\$env:USERNAME" /tr "`"$($ActionFetch.Execute)`" `"$($ActionFetch.Arguments)`"" /f 2>$null
schtasks /create /tn "\CyberWatch\CyberWatch-Fetch30" /sc MINUTE /mo 30 /ru "$env:USERDOMAIN\$env:USERNAME" /tr "`"$($ActionFetch.Execute)`" `"$($ActionFetch.Arguments)`"" /f 2>$null
Write-Host "[OK] Collecte: au logon + toutes les 30 min" -ForegroundColor Green

# Task 2: purge every Sunday 00:00 (favoris preserves)
try { Unregister-ScheduledTask -TaskPath "\CyberWatch\" -TaskName "CyberWatch-WeeklyPurge" -Confirm:$false -ErrorAction SilentlyContinue } catch {}
schtasks /create /tn "\CyberWatch\CyberWatch-WeeklyPurge" /sc WEEKLY /d SUN /st 00:00 /ru "$env:USERDOMAIN\$env:USERNAME" /tr "`"$($ActionPurge.Execute)`" `"$($ActionPurge.Arguments)`"" /f 2>$null
Write-Host "[OK] Purge: chaque dimanche 00h00 (favoris preserves)" -ForegroundColor Green
Write-Host ""
Write-Host "Automatisation CyberWatch active." -ForegroundColor Cyan
Write-Host "  - Collecte : au demarrage + toutes les 30 min" -ForegroundColor Cyan
Write-Host "  - Purge    : dimanche 00h00 (articles > 7 jours supprimes, favoris gardes)" -ForegroundColor Cyan
Write-Host "Pour desinstaller : scripts\uninstall_task.ps1" -ForegroundColor Cyan
