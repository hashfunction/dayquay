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

# Failure capture is read-only: it must never focus/move a window and may read
# pixels only for the exact already-foreground owned dialog.
foreach($case in @('partial-bottom','owned','partial-negative-monitor','foreign','wrong-hwnd','wrong-title','hidden','foreign-foreground','outside-desktop','oversized','changed-after-capture','desktop-changed','capture-error')) {
    $script:failureObservation=@{process_id=123;window_handle=17;title='Select a directory';visible=$true;foreground_window_handle=17;
        bounds=@{x=20;y=30;width=600;height=400};virtual_screen=@{x=0;y=0;width=1024;height=768}}
    $script:failureCaptures=0
    $script:capturedBounds=$null
    $operations=@{
        Observe={return ($script:failureObservation | ConvertTo-Json -Depth 5 | ConvertFrom-Json -AsHashtable)}
        Capture={param($bounds) $script:failureCaptures++; $script:capturedBounds=$bounds; return [byte[]](1,2,3)}
    }
    switch($case) {
        foreign {$script:failureObservation.process_id=999}
        wrong-hwnd {$script:failureObservation.window_handle=18}
        wrong-title {$script:failureObservation.title='Other'}
        hidden {$script:failureObservation.visible=$false}
        foreign-foreground {$script:failureObservation.foreground_window_handle=99}
        partial-bottom {$script:failureObservation.bounds=@{x=17;y=0;width=1006;height=781}}
        partial-negative-monitor {$script:failureObservation.virtual_screen.x=-1024;$script:failureObservation.bounds=@{x=-1050;y=30;width=600;height=400}}
        outside-desktop {$script:failureObservation.bounds.x=2000}
        desktop-changed {$operations.Capture={param($bounds) $script:failureCaptures++;$script:failureObservation.virtual_screen.width=1023;return [byte[]](1,2,3)}}
        oversized {$script:failureObservation.bounds.width=3000}
        changed-after-capture {$operations.Capture={param($bounds) $script:failureCaptures++;$script:failureObservation.foreground_window_handle=99;return [byte[]](1,2,3)}}
        capture-error {$operations.Capture={param($bounds) $script:failureCaptures++;throw 'capture failed'}}
    }
    $details=@{};$failure=$null;$bytes=$null
    try {$bytes=Invoke-DayQuayFailureCapture 123 17 'Select a directory' $operations $details} catch {$failure=$_.Exception.Message}
    if (($case -in @('owned','partial-bottom','partial-negative-monitor')) -eq [bool]$failure) {throw "Failure capture result differs: $case / $failure"}
    if ($case -eq 'owned' -and ($bytes.Count -ne 3 -or $script:failureCaptures -ne 1)) {throw 'Owned dialog was not captured exactly once'}
    if ($case -notin @('owned','partial-bottom','partial-negative-monitor','changed-after-capture','desktop-changed','capture-error') -and $script:failureCaptures) {throw "Unowned/unbounded pixels were captured: $case"}
    if ($case -eq 'partial-bottom' -and ($script:capturedBounds.x -ne 17 -or $script:capturedBounds.y -ne 0 -or
        $script:capturedBounds.width -ne 1006 -or $script:capturedBounds.height -ne 768 -or $details.fully_visible)) {throw 'Partial dialog capture did not preserve the measured visible intersection'}
    if ($case -eq 'partial-negative-monitor' -and ($script:capturedBounds.x -ne -1024 -or $script:capturedBounds.width -ne 574 -or $details.fully_visible)) {throw 'Negative-monitor intersection incorrect'}
    if ($case -eq 'owned' -and -not $details.fully_visible) {throw 'Fully visible diagnostic was mislabeled'}
    if ($failure -and $null -ne $bytes) {throw "Rejected capture returned pixels: $case"}
}
Write-Output 'PASS failure-only capture: exact owner/foreground/bounds, post-capture recheck, and native capture error'

# Execute the actual consumer try/catch, replacing only native invocation and
# screenshot adapters, to prove diagnostics cannot replace the primary error.
$installAst=(Get-Command Invoke-DayQuayInstallQualification).ScriptBlock.Ast
$consumerTry=@($installAst.FindAll({param($node)
    $node -is [Management.Automation.Language.TryStatementAst] -and
    $node.Body.Extent.Text -match "'installed_workflow_qualification.py'"
},$true))
if ($consumerTry.Count -ne 1) {throw 'Cannot locate the exact consumer diagnostic catch'}
foreach($diagnosticFailure in @($false,$true)) {
    & {
        $state=@{process=(Get-Process -Id $PID);expectedTitle='DayQuay';workflowProfile=@{root='fixture-profile'};
            workflowArchive='fixture.zip';workflowRestoreName='Restored';workflowSentinel='sentinel';workflowReopenMarker='reopen';
            output='fixture-output';workflowDiagnosticError=$null}
        $workflowEvidencePath='fixture-output/installed-consumer-workflow.json';$diagnosticCalls=@{count=0}
        function Get-DayQuayPackagingPython {return 'fixture-python'}
        function Invoke-CheckedNative {throw 'original consumer failure'}
        function Write-DayQuayConsumerWindowFailure {
            $diagnosticCalls.count++
            if ($diagnosticFailure) {throw 'diagnostic failure'}
        }
        $failure=$null
        # A real .ps1 file provides PSScriptRoot as in the production helper.
        $consumerScript=Join-Path ([IO.Path]::GetTempPath()) ('dayquay-consumer-catch-'+[guid]::NewGuid().ToString('N')+'.ps1')
        Write-NewUtf8Text $consumerScript $consumerTry[0].Extent.Text
        try {& $consumerScript} catch {$failure=$_.Exception.Message} finally {Remove-Item -LiteralPath $consumerScript}
        if ($failure -cne 'original consumer failure' -or $diagnosticCalls.count -ne 1) {throw "Consumer failure was masked or diagnostics were not attempted exactly once: $failure / calls=$($diagnosticCalls.count)"}
        if ([bool]$state.workflowDiagnosticError -ne $diagnosticFailure) {throw 'Diagnostic error was not retained separately'}
    }
}
Write-Output 'PASS actual consumer catch preserves original error when failure capture succeeds or fails'
