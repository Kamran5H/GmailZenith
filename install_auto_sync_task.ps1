# Gmail Zenith Pro - Windows Scheduled Task Installer for Auto-Sync
# Runs silently on user login to keep inbox clean automatically

$taskName = "GmailZenithAutoSync"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$vbsPath = Join-Path $scriptDir "launch_auto_sync.vbs"

Write-Host "Registering Windows Scheduled Task for Gmail Zenith Auto-Sync..." -ForegroundColor Cyan
Write-Host "Target: $vbsPath" -ForegroundColor Gray

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbsPath`"" -WorkingDirectory $scriptDir
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Days 365)

try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Gmail Zenith Pro Background Auto-Cleaner"
    Write-Host "[SUCCESS] Scheduled Task '$taskName' successfully registered!" -ForegroundColor Green
    Write-Host "Gmail Zenith will now automatically keep your inbox clean 24/7." -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Could not register scheduled task: $_" -ForegroundColor Yellow
}
