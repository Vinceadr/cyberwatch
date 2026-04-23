# CyberWatch - Remove scheduled tasks
try { Unregister-ScheduledTask -TaskPath "\CyberWatch\" -TaskName "CyberWatch-Fetch" -Confirm:$false -ErrorAction SilentlyContinue } catch {}
try { Unregister-ScheduledTask -TaskPath "\CyberWatch\" -TaskName "CyberWatch-WeeklyPurge" -Confirm:$false -ErrorAction SilentlyContinue } catch {}
Write-Host "Taches CyberWatch supprimees." -ForegroundColor Yellow
