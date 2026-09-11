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
