# Copyright 2026 Trieflow LLC. MIT. Execute production snapshot and cleanup boundaries.
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'capture_helpers.ps1')
function Check($Value,[string]$Message) {if (-not $Value) {throw $Message}}
Add-JotCaptureTypes
Check ([Runtime.InteropServices.Marshal]::SizeOf([JotmorrowMarketing.Window+RECT]::new()) -eq 16) 'Native RECT ABI differs.'
$plan=Get-JotCaptureWindowPlan @{X=0;Y=0;Width=1920;Height=1040}
Check ($plan.width -eq 1440 -and $plan.height -eq 900 -and $plan.x -eq 240 -and $plan.y -eq 70) 'Native window plan differs.'
foreach ($area in @(@{X=0;Y=0;Width=1024;Height=768},@{X=0;Y=0;Width=1440;Height=899})) {
    $failed=$false;try {$null=Get-JotCaptureWindowPlan $area}catch {$failed=$true};Check $failed 'Clipped native display accepted.'
}
$baseline=@{process_id=42;main_pid=42;target_pid=42;main_handle=101;target_handle=102;foreground_handle=102;
    main_title='Jotmorrow - Saturday, 9/12/2026';target_title='Restore portable backup';main_visible=$true;target_visible=$true;dpi=96;
    main_bounds=@{x=240;y=70;width=1440;height=900};target_bounds=@{x=700;y=380;width=520;height=200};
    display=@{x=0;y=0;width=1920;height=1080};work_area=@{x=0;y=0;width=1920;height=1040}}
function Copy-Baseline {return ($baseline|ConvertTo-Json -Depth 8|ConvertFrom-Json -AsHashtable)}
$script:current=Copy-Baseline;$script:captureCalls=0
$ops=@{Observe={return $script:current};Capture={param($bounds)$script:captureCalls++;return ,[byte[]]@(1,2,3)}}
$result=Invoke-JotFrameCapture $ops 42 101 102 $baseline.main_title $baseline.target_title
Check ($result.bytes.Length -eq 3 -and $script:captureCalls -eq 1) 'Owned modal frame did not pass.'
$mutations=@{process_id=43;main_pid=43;target_pid=43;main_handle=103;target_handle=104;foreground_handle=101;
    main_title='Foreign';target_title='Unknown dialog';main_visible=$false;target_visible=$false;dpi=120}
foreach ($key in $mutations.Keys) {
    $script:current=Copy-Baseline;$script:current[$key]=$mutations[$key];$script:captureCalls=0;$failed=$false
    try {$null=Invoke-JotFrameCapture $ops 42 101 102 $baseline.main_title $baseline.target_title}catch {$failed=$true}
    Check ($failed -and $script:captureCalls -eq 0) "Foreign snapshot reached screenshot bytes: $key"
}
foreach ($which in @('small-main','clipped-main','clipped-dialog','nonfinite')) {
    $script:current=Copy-Baseline
    switch ($which) {'small-main' {$script:current.main_bounds.width=992};'clipped-main' {$script:current.main_bounds.x=900};
        'clipped-dialog' {$script:current.target_bounds.x=1700};'nonfinite' {$script:current.main_bounds.x=[double]::NaN}}
    $script:captureCalls=0;$failed=$false;try {$null=Invoke-JotFrameCapture $ops 42 101 102 $baseline.main_title $baseline.target_title}catch {$failed=$true}
    Check ($failed -and $script:captureCalls -eq 0) "Invalid geometry reached screenshot bytes: $which"
}
$script:current=Copy-Baseline;$script:observations=0
$changed=@{Observe={$script:observations++;$copy=Copy-Baseline;if($script:observations -gt 1){$copy.target_bounds.x++};return $copy};Capture={param($bounds)return ,[byte[]]@(1,2,3)}}
$failed=$false;try {$null=Invoke-JotFrameCapture $changed 42 101 102 $baseline.main_title $baseline.target_title}catch {$failed=$true}
Check $failed 'Window mutation during capture was accepted.'
# Failed Add must not grant ownership of a matching registration; an active
# unowned broker process must not grant authority to remove its profile.
$state=@{driver=$null;process=$null;processOwned=$false;cleanupProcessExit=$null;processShutdownVerified=$false;installAttempted=$true;
    installedByUs=$false;ownedPackageFullName=$null;addCompleted=$false;residualPackageFullNames=@();trustAttempted=$false;certificate=$null;
    workflowProfile=@{root='owned-fixture'};brokerProcessId=42;profileRemoved=$false;temporary=$null;cleanupErrors=[Collections.Generic.List[string]]::new()}
$script:removed=0;$script:profileRemoved=0
function Get-AppxPackage {param($Name) return [pscustomobject]@{PackageFullName='1659hashfunction.DayQuay_1.0.1.0_x64__r3hxytd7jt6c4'}}
function Remove-AppxPackage {param($Package)$script:removed++}
function Remove-DayQuayWorkflowProfile($Ownership) {$script:profileRemoved++;return $true}
Complete-JotCaptureCleanup $state
Check ($script:removed -eq 0 -and $script:profileRemoved -eq 0 -and $state.cleanupErrors.Count -eq 2) 'Unproven package/profile cleanup was permitted.'
Write-Output 'PASS: native ABI/window plan, owned modal frame, 16 refusal/mutation cases, failed-Add and unproven-process cleanup guards.'
