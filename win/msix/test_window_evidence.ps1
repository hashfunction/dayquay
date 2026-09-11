# Copyright 2026 Trieflow LLC. MIT. Observation-policy fixtures, not GUI execution.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'qualify-msix-install.ps1') -LibraryOnly
$title='DayQuay - Friday, 9/11/2026' # Actual retained Windows receipt; synthetic UI observations below.
$good=[ordered]@{ title=$title; expected_title=$title; process_id=123; visible=$true; width=800; height=600;
    screenshot_captured=$true; screenshot_sha256=('a'*64); sampled_colors=50;
    startup_limited=$true; actionable_controls_verified=$false;
    accessibility_scope='GTK startup only; journal/backup/restore workflows untested'; controls=@();
    top_level_windows=@([ordered]@{name=$title;offscreen=$false}) }
# GTK3 may expose only its window to UIA. This is explicit limited startup
# evidence, never a claim that a journal or backup control was exercised.
Assert-DayQuayWindowEvidence $good $title
foreach ($case in @('title','hidden','no-screenshot','blank-screenshot','small-window','unbounded-window','false-workflow','missing-limit','modal')) {
    $probe=$good | ConvertTo-Json -Depth 8 | ConvertFrom-Json -AsHashtable
    switch ($case) {
        title {$probe.title='DayQuay fatal error'}
        hidden {$probe.visible=$false}
        no-screenshot {$probe.screenshot_captured=$false}
        blank-screenshot {$probe.sampled_colors=1}
        small-window {$probe.width=50}
        unbounded-window {$probe.width=20000}
        false-workflow {$probe.actionable_controls_verified=$true}
        missing-limit {$probe.startup_limited=$false}
        modal {$probe.top_level_windows+=@{name='Error';offscreen=$false}}
    }
    $rejected=$false
    try { Assert-DayQuayWindowEvidence $probe $title } catch { $rejected=$true }
    if (-not $rejected) { throw "Invalid observation accepted: $case" }
}
Write-Output 'PASS GTK window-observation policy: explicit limited fixture and nine negative variants'

foreach ($wrong in @('DayQuay','DayQuay - loading','DayQuay error',($title+' '),($title+' - error'),('prefix '+$title),'DayQuay - Saturday, 9/12/2026','')) {
    if (Test-DayQuayWindowTitle $wrong $title) { throw "Strict source-derived title accepted unrelated/transient title: $wrong" }
}
if (Test-DayQuayWindowTitle 'DayQuay' '') { throw 'Missing expected title accepted' }
Write-Output 'PASS exact stable date-title contract and eight transient/error/prefix/date variants'

# Exercise the actual fit/reobserve operation with finite desktop observations.
# Native screen/window calls alone are adapters; no GUI execution is claimed.
$script:observation=@{process_id=123;title=$title;visible=$true;
    bounds=@{x=0;y=0;width=1040;height=739};work_area=@{x=0;y=0;width=1024;height=728}}
$script:moves=[Collections.Generic.List[object]]::new()
$ops=@{
    Observe={return ($script:observation | ConvertTo-Json -Depth 6 | ConvertFrom-Json -AsHashtable)}
    Move={param($bounds) $script:moves.Add($bounds);$script:observation.bounds=$bounds}
    Wait={}
}
$geometry=@{}
Set-DayQuayCapturePlacement 123 $title $ops $geometry
if($script:moves.Count -ne 1 -or -not $geometry.adjusted -or $geometry.before.bounds.width -ne 1040 -or $geometry.after.bounds.width -ne 992 -or
    $geometry.after.bounds.height -ne 696 -or $geometry.after.bounds.x -ne 16 -or $geometry.after.bounds.y -ne 16){throw 'Oversized native-window fixture was not fitted inside the work area.'}
Assert-DayQuayCaptureBounds $geometry.after.bounds $geometry.after.work_area

foreach($case in @('fits','negative-monitor','offscreen-location','foreign','wrong-title','hidden','minimum-refused','small-desktop','nonfinite','move-failed','foreign-after-move','title-after-move','nonfinite-desktop','oversize')){
    $script:observation=@{process_id=123;title=$title;visible=$true;
        bounds=@{x=10;y=20;width=800;height=600};work_area=@{x=0;y=0;width=1024;height=728}}
    $script:moves.Clear()
    $ops.Move={param($bounds) $script:moves.Add($bounds);$script:observation.bounds=$bounds}
    $expectedFailure=$false
    switch($case){
        negative-monitor {$script:observation.work_area.x=-1920;$script:observation.bounds.x=-2000}
        offscreen-location {$script:observation.bounds.x=900}
        foreign {$script:observation.process_id=456;$expectedFailure=$true}
        wrong-title {$script:observation.title='Error';$expectedFailure=$true}
        hidden {$script:observation.visible=$false;$expectedFailure=$true}
        minimum-refused {$script:observation.bounds.width=1040;$ops.Move={param($bounds) $script:moves.Add($bounds)};$expectedFailure=$true}
        small-desktop {$script:observation.work_area.width=300;$expectedFailure=$true}
        nonfinite {$script:observation.bounds.x=[double]::NaN;$expectedFailure=$true}
        move-failed {$script:observation.bounds.x=900;$ops.Move={throw 'Native move failed'};$expectedFailure=$true}
        foreign-after-move {$script:observation.bounds.x=900;$ops.Move={param($bounds) $script:observation.bounds=$bounds;$script:observation.process_id=456};$expectedFailure=$true}
        title-after-move {$script:observation.bounds.x=900;$ops.Move={param($bounds) $script:observation.bounds=$bounds;$script:observation.title='Error'};$expectedFailure=$true}
        nonfinite-desktop {$script:observation.work_area.width=[double]::PositiveInfinity;$expectedFailure=$true}
        oversize {$script:observation.bounds.width=9000;$expectedFailure=$true}
    }
    $geometry=@{};$failure=$null
    try{Set-DayQuayCapturePlacement 123 $title $ops $geometry}catch{$failure=$_.Exception.Message}
    if([bool]$failure -ne $expectedFailure){throw "Placement result differs: $case / $failure"}
    if(-not $failure){Assert-DayQuayCaptureBounds $geometry.after.bounds $geometry.after.work_area}
    if($case -eq 'fits' -and $script:moves.Count -ne 0){throw 'Already visible window was moved unnecessarily'}
    if($case -in @('foreign','wrong-title','hidden','small-desktop','nonfinite','nonfinite-desktop','oversize') -and $script:moves.Count -ne 0){throw "Unqualified window/desktop was moved: $case"}
    if($case -eq 'minimum-refused' -and $geometry.after.bounds.width -ne 1040){throw 'A requested size was substituted for the refused observed size'}
}
Write-Output 'PASS actual placement operation: oversized window plus fourteen fit/identity/desktop/failure cases; native Win32 move remains unexecuted locally'

Add-DayQuayActivationTypes
$move=[DayQuayQualification.NativePackageProbe].GetMethod('SetWindowPos')
if($move.ReturnType -ne [bool] -or $move.GetParameters().Count -ne 7){throw 'Native SetWindowPos signature differs'}
$capture=(Get-Command Get-WindowQualification).ScriptBlock.Ast
$fitCalls=@($capture.FindAll({param($node) $node -is [Management.Automation.Language.CommandAst] -and $node.GetCommandName() -eq 'Set-DayQuayCapturePlacement'},$true))
$copies=@($capture.FindAll({param($node) $node -is [Management.Automation.Language.InvokeMemberExpressionAst] -and $node.Member.Value -eq 'CopyFromScreen'},$true))
if($fitCalls.Count -ne 1 -or $copies.Count -ne 1 -or $fitCalls[0].Extent.StartOffset -gt $copies[0].Extent.StartOffset){throw 'Production screenshot path does not fit/reobserve before screen capture'}
Write-Output 'PASS production screenshot wiring and native declaration compilation; no Win32 invocation on macOS'
