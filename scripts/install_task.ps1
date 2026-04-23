# CyberWatch - Windows Task Scheduler Automation
$ErrorActionPreference = "Stop"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$PythonExe  = (Get-Command python -ErrorAction SilentlyContinue).Source
$ExePath = Join-Path $ProjectDir "dist\CyberWatch\CyberWatch.exe"
$UseExe  = Test-Path $ExePath
if ($UseExe) {
    $ActionFetch = New-ScheduledTaskAction -Execute $ExePath -Argument "--pipeline"
    $ActionPurge = New-ScheduledTaskAction -Execute $ExePath -Argument "--pipeline"
} else {
    if (-not $PythonExe) { throw "Python introuvable dans PATH." }
    $RunScript   = Join-Path $ScriptDir "run_pipeline.py"
    $ActionFetch = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$RunScript`"" -WorkingDirectory $ProjectDir
    $ActionPurge = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$RunScript`"" -WorkingDirectory $ProjectDir
}
$Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Limited -LogonType Interactive
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$TriggerRepeat = (New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 30) -Once -At (Get-Date)).Repetition
$TriggerLogon.Repetition = $TriggerRepeat
try { Unregister-ScheduledTask -TaskPath "\CyberWatch\" -TaskName "CyberWatch-Fetch" -Confirm:$false -ErrorAction SilentlyContinue } catch {}
Register-ScheduledTask -TaskName "CyberWatch-Fetch" -TaskPath "\CyberWatch\" -Action $ActionFetch -Trigger $TriggerLogon -Settings $Settings -Principal $Principal -Description "CyberWatch collecte les articles toutes les 30 minutes" | Out-Null
Write-Host "[OK] Tache 'CyberWatch-Fetch' enregistree (30 min apres chaque logon)" -ForegroundColor Green
$TriggerWeekly = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "00:00"
try { Unregister-ScheduledTask -TaskPath "\CyberWatch\" -TaskName "CyberWatch-WeeklyPurge" -Confirm:$false -ErrorAction SilentlyContinue } catch {}
Register-ScheduledTask -TaskName "CyberWatch-WeeklyPurge" -TaskPath "\CyberWatch\" -Action $ActionPurge -Trigger $TriggerWeekly -Settings $Settings -Principal $Principal -Description "CyberWatch purge hebdomadaire dimanche 00h00" | Out-Null
Write-Host "[OK] Tache 'CyberWatch-WeeklyPurge' enregistree (dimanche 00:00)" -ForegroundColor Green
Write-Host "CyberWatch collectera automatiquement les articles a chaque demarrage." -ForegroundColor Cyan
