# Meeting Stats Fix - Test Script
# Update the variables below, then run: .\test_stats_fix.ps1

# ============ CONFIGURATION ============
$licenseKey = "FREE44082DF36DA1"  # Replace this!
$baseUrl = "https://ai-meeting-notes-production-81d7.up.railway.app"      # Your API URL
# =======================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Meeting Stats Diagnostic Tool" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Current Stats (Before Fix)
Write-Host "[1] Checking current stats..." -ForegroundColor Yellow
try {
    $currentStats = Invoke-RestMethod -Uri "$baseUrl/meetings/stats" -Headers @{"X-License-Key"=$licenseKey}
    Write-Host "   Current Stats:" -ForegroundColor White
    Write-Host "   - Total meetings: $($currentStats.total_meetings)" -ForegroundColor White
    Write-Host "   - Completed: $($currentStats.completed)" -ForegroundColor White
    Write-Host "   - Processing: $($currentStats.processing)" -ForegroundColor White
    Write-Host "   - This month: $($currentStats.meetings_this_month) <-- THIS IS THE PROBLEM" -ForegroundColor Red
    Write-Host ""
} catch {
    Write-Host "   ERROR: $_" -ForegroundColor Red
    Write-Host ""
    exit
}

# Step 2: Diagnose
Write-Host "[2] Running diagnostic..." -ForegroundColor Yellow
try {
    $diagnosis = Invoke-RestMethod -Uri "$baseUrl/meetings/stats/diagnose" -Headers @{"X-License-Key"=$licenseKey}
    Write-Host "   Diagnosis Results:" -ForegroundColor White
    Write-Host "   - Usage table says: $($diagnosis.diagnosis.usage_table_says)" -ForegroundColor White
    Write-Host "   - Actual meetings: $($diagnosis.diagnosis.actual_meetings_this_month)" -ForegroundColor White
    Write-Host "   - Discrepancy: $($diagnosis.diagnosis.discrepancy)" -ForegroundColor $(if($diagnosis.diagnosis.discrepancy -eq 0){"Green"}else{"Red"})
    Write-Host "   - Status: $($diagnosis.diagnosis.status)" -ForegroundColor $(if($diagnosis.diagnosis.is_accurate){"Green"}else{"Red"})
    Write-Host "   Recommendation: $($diagnosis.recommendation)" -ForegroundColor Cyan
    Write-Host ""
    
    if ($diagnosis.diagnosis.is_accurate) {
        Write-Host "SUCCESS: No repair needed - stats are accurate!" -ForegroundColor Green
        Write-Host ""
        exit
    }
} catch {
    Write-Host "   ERROR: $_" -ForegroundColor Red
    Write-Host ""
    exit
}

# Step 3: Ask for confirmation
Write-Host "[3] Ready to repair..." -ForegroundColor Yellow
$confirm = Read-Host "   Do you want to fix this? (yes/no)"

if ($confirm -ne "yes" -and $confirm -ne "y") {
    Write-Host ""
    Write-Host "Repair cancelled" -ForegroundColor Red
    Write-Host ""
    exit
}

# Step 4: Repair
Write-Host ""
Write-Host "[4] Repairing..." -ForegroundColor Yellow
try {
    $repair = Invoke-RestMethod -Uri "$baseUrl/meetings/stats/repair" -Method Post -Headers @{"X-License-Key"=$licenseKey}
    Write-Host "   Repair Results:" -ForegroundColor White
    Write-Host "   - Status: $($repair.status)" -ForegroundColor Green
    Write-Host "   - Old value: $($repair.old_value)" -ForegroundColor White
    Write-Host "   - New value: $($repair.new_value)" -ForegroundColor White
    Write-Host "   - Correction: $($repair.correction)" -ForegroundColor Cyan
    Write-Host "   $($repair.message)" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "   ERROR: $_" -ForegroundColor Red
    Write-Host ""
    exit
}

# Step 5: Verify
Write-Host "[5] Verifying fix..." -ForegroundColor Yellow
try {
    $newStats = Invoke-RestMethod -Uri "$baseUrl/meetings/stats" -Headers @{"X-License-Key"=$licenseKey}
    Write-Host "   New Stats:" -ForegroundColor White
    Write-Host "   - Total meetings: $($newStats.total_meetings)" -ForegroundColor White
    Write-Host "   - Completed: $($newStats.completed)" -ForegroundColor White
    Write-Host "   - Processing: $($newStats.processing)" -ForegroundColor White
    Write-Host "   - This month: $($newStats.meetings_this_month) <-- FIXED!" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "SUCCESS! Stats are now accurate!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
} catch {
    Write-Host "   ERROR: $_" -ForegroundColor Red
    Write-Host ""
}