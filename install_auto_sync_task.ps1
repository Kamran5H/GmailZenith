# Gmail Zenith - registers a Windows Scheduled Task that starts the
# background Auto-Clean daemon at logon. Rules and interval are set on the
# dashboard's Auto-Clean tab.
#
#   Install:    powershell -ExecutionPolicy Bypass -File install_auto_sync_task.ps1
#   Uninstall:  powershell -ExecutionPolicy Bypass -File install_auto_sync_task.ps1 -Uninstall

param([switch]$Uninstall)

$taskName = "GmailZenithAutoSync"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK] Removed scheduled task '$taskName'." -ForegroundColor Green
    exit 0
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$vbsPath = Join-Path $scriptDir "launch_auto_sync.vbs"

Write-Host "Registering scheduled task '$taskName'..." -ForegroundColor Cyan
Write-Host "Target: $vbsPath" -ForegroundColor Gray

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbsPath`"" -WorkingDirectory $scriptDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)

try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Gmail Zenith background Auto-Clean" | Out-Null
    Write-Host "[OK] Auto-Clean will start automatically every time you log in." -ForegroundColor Green
    Start-ScheduledTask -TaskName $taskName
    Write-Host "[OK] Started now." -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Could not register the scheduled task: $_" -ForegroundColor Yellow
}
