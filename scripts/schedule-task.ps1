# ==============================================================================
# FindMyBoss - Windows Task Scheduler Automation Helper
# ==============================================================================
# Usage:
#   .\scripts\schedule-task.ps1 -Register -DailyTime "22:00"
#   .\scripts\schedule-task.ps1 -RunNow
#   .\scripts\schedule-task.ps1 -Status
#   .\scripts\schedule-task.ps1 -Unregister
# ==============================================================================

param(
    [switch]$Register,
    [switch]$RunNow,
    [switch]$Status,
    [switch]$Unregister,
    [switch]$TodayOnly,
    [string]$DailyTime = "22:00",
    [string]$TaskName = "FindMyBoss_DailyScraper"
)

$ProjectDir = (Get-Item "$PSScriptRoot\..").FullName
$BatScript = Join-Path $ProjectDir "scripts\run-scraper.bat"

if (-not (Test-Path $BatScript)) {
    Write-Error "Khong tim thay tap tin: $BatScript"
    exit 1
}

# If no specific switch provided, show usage help
if (-not ($Register -or $RunNow -or $Status -or $Unregister)) {
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "🎯 FindMyBoss Task Scheduler Manager" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "Lenh su dung:"
    Write-Host "  .\scripts\schedule-task.ps1 -Register -DailyTime '22:00'             # Dang ky lich chay hang ngay (doc tu scraper_config.json)"
    Write-Host "  .\scripts\schedule-task.ps1 -Register -DailyTime '22:00' -TodayOnly  # Dang ky lich chay bat buoc chi cao tin hom nay (--today)"
    Write-Host "  .\scripts\schedule-task.ps1 -Status                                 # Kiem tra trang thai task"
    Write-Host "  .\scripts\schedule-task.ps1 -RunNow                                 # Chay thu nghiem task ngay lap tuc"
    Write-Host "  .\scripts\schedule-task.ps1 -Unregister                             # Xoa task khoi Task Scheduler"
    Write-Host "==========================================================" -ForegroundColor Cyan
    exit 0
}

# 1. Kiem tra trang thai (Status)
if ($Status) {
    Write-Host "[*] Dang kiem tra tac vu: $TaskName..." -ForegroundColor Cyan
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "✅ Tac vu [$TaskName] dang ton tai!" -ForegroundColor Green
        Write-Host "   - Trang thai: $($task.State)"
        Write-Host "   - Lan chay cuoi: $($taskInfo.LastRunTime) (Ket qua: $($taskInfo.LastTaskResult))"
        Write-Host "   - Lan chay tiep theo: $($taskInfo.NextRunTime)"
    } else {
        Write-Host "⚠️  Khong tim thay tac vu [$TaskName] trong Task Scheduler." -ForegroundColor Yellow
    }
}

# 2. Xoa tac vu (Unregister)
if ($Unregister) {
    Write-Host "[*] Dang huy dang ky tac vu: $TaskName..." -ForegroundColor Cyan
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "✅ Da xoa tac vu [$TaskName] thanh cong." -ForegroundColor Green
}

# 3. Dang ky tac vu moi (Register)
if ($Register) {
    Write-Host "[*] Dang cau hinh tac vu [$TaskName] chay hang ngay vao $DailyTime..." -ForegroundColor Cyan
    
    $BatArgs = if ($TodayOnly) { "/c `"$BatScript`" --today" } else { "/c `"$BatScript`"" }
    $Action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument $BatArgs `
        -WorkingDirectory $ProjectDir

    # Trigger: Chay hang ngay vao gio chi dinh
    $Trigger = New-ScheduledTaskTrigger -Daily -At $DailyTime

    # Settings: Cho phep chay bu khi bi lo lich (StartWhenAvailable), chay bang pin, gioi han 2 tieng
    $Settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2)

    # Register task for current user
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description "Tu dong chay script cao viec FindMyBoss moi ngay" `
        -Force | Out-Null

    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "✅ DANG KY LICH CHAY HANG NGAY THANH CONG!" -ForegroundColor Green
    Write-Host "   - Ten tac vu: $TaskName"
    Write-Host "   - Thoi gian chay: Hang ngay vao luc $DailyTime"
    Write-Host "   - Tap tin thuc thi: $BatScript"
    Write-Host "   - Thu muc lam viec: $ProjectDir"
    Write-Host "   - Log ghi tai: $ProjectDir\logs\crawl_log.txt"
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "💡 Meo: Ban co the chay test ngay bang lenh:"
    Write-Host "   .\scripts\schedule-task.ps1 -RunNow" -ForegroundColor Yellow
}

# 4. Chay ngay (RunNow)
if ($RunNow) {
    Write-Host "[*] Dang kich hoat chay tac vu [$TaskName]..." -ForegroundColor Cyan
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Warning "Tac vu chua duoc dang ky. Dang tien hanh dang ky truoc..."
        & $PSCommandPath -Register -DailyTime $DailyTime
    }
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "🚀 Da khoi chay tac vu trong nen!" -ForegroundColor Green
    Write-Host "   Ban co the kiem tra log tai: $ProjectDir\logs\crawl_log.txt" -ForegroundColor Yellow
}
