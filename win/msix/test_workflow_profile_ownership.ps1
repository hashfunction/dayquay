# Real disposable profile preparation and cleanup ownership tests.
# Copyright 2026 Trieflow LLC. MIT.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'qualify-msix-install.ps1') -LibraryOnly

$probe=Join-Path ([IO.Path]::GetTempPath()) ('dayquay-workflow-profile-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $probe | Out-Null
try {
    $profile=Join-Path $probe 'DayQuay'
    $owned=New-DayQuayWorkflowProfile $profile ([guid]::NewGuid().ToString('N'))
    if (-not (Test-Path -LiteralPath (Join-Path $profile 'data') -PathType Container) -or
        -not (Test-Path -LiteralPath (Join-Path $profile 'ReopenProbe') -PathType Container) -or
        (Get-Content -LiteralPath (Join-Path $profile 'configuration.cfg') -Raw) -cne "firstStart=0`n" -or
        (Get-FileHash -LiteralPath $owned.marker -Algorithm SHA256).Hash.ToLowerInvariant() -cne $owned.marker_sha256) {
        throw 'Owned workflow profile contents differ.'
    }
    $collision=$false
    try { New-DayQuayWorkflowProfile $profile ([guid]::NewGuid().ToString('N')) | Out-Null }
    catch { $collision=$_.Exception.Message -match 'must be preserved' }
    if (-not $collision -or -not (Test-Path -LiteralPath $owned.marker)) { throw 'Existing profile collision was not preserved.' }
    if (-not (Remove-DayQuayWorkflowProfile $owned) -or (Test-Path -LiteralPath $profile)) { throw 'Exact owned profile was not removed.' }

    $tampered=New-DayQuayWorkflowProfile $profile ([guid]::NewGuid().ToString('N'))
    [IO.File]::WriteAllText($tampered.marker,'foreign replacement')
    $rejected=$false
    try { Remove-DayQuayWorkflowProfile $tampered | Out-Null }
    catch { $rejected=$_.Exception.Message -match 'marker changed' }
    if (-not $rejected -or -not (Test-Path -LiteralPath $profile)) { throw 'Changed ownership marker did not preserve the profile.' }

    Remove-Item -LiteralPath $profile -Recurse -Force
    $actualWriter=${function:Write-NewUtf8Text}
    $script:PreparationFailure='partial'
    $script:ReplacementRoot=$profile
    $script:ReplacementOriginal=Join-Path $probe 'original-profile'
    $script:ReplacementTarget=Join-Path $probe 'foreign-profile'
    function Write-NewUtf8Text([string]$Path,[string]$Value) {
        if ([IO.Path]::GetFileName($Path) -ceq '.dayquay-qualification-owner' -and
            $script:PreparationFailure -eq 'replacement-before-marker') {
            Move-Item -LiteralPath $script:ReplacementRoot -Destination $script:ReplacementOriginal
            New-Item -ItemType $(if ($IsWindows) { 'Junction' } else { 'SymbolicLink' }) `
                -Path $script:ReplacementRoot -Target $script:ReplacementTarget | Out-Null
            throw 'controlled replacement before marker failure'
        }
        if ([IO.Path]::GetFileName($Path) -ceq 'configuration.cfg') {
            if ($script:PreparationFailure -eq 'replacement') {
                Move-Item -LiteralPath $script:ReplacementRoot -Destination $script:ReplacementOriginal
                New-Item -ItemType $(if ($IsWindows) { 'Junction' } else { 'SymbolicLink' }) `
                    -Path $script:ReplacementRoot -Target $script:ReplacementTarget | Out-Null
            }
            throw "controlled $($script:PreparationFailure) construction failure"
        }
        & $actualWriter $Path $Value
    }
    try {
        $partialFailure=$null
        try { New-DayQuayWorkflowProfile $profile ([guid]::NewGuid().ToString('N')) | Out-Null }
        catch { $partialFailure=$_.Exception.Message }
        if ($partialFailure -notmatch 'controlled partial construction failure' -or
            (Test-Path -LiteralPath $profile)) {
            throw 'Guarded cleanup did not remove the still-owned partial profile.'
        }

        New-Item -ItemType Directory -Path $script:ReplacementTarget | Out-Null
        [IO.File]::WriteAllText((Join-Path $script:ReplacementTarget 'foreign.txt'),'preserve')
        $script:PreparationFailure='replacement'
        $replacementFailure=$null
        try { New-DayQuayWorkflowProfile $profile ([guid]::NewGuid().ToString('N')) | Out-Null }
        catch { $replacementFailure=$_.Exception.Message }
        if ($replacementFailure -notmatch 'preparation cleanup.*preserved' -or
            -not (Test-Path -LiteralPath $profile) -or
            (Get-Content -LiteralPath (Join-Path $script:ReplacementTarget 'foreign.txt') -Raw) -cne 'preserve') {
            throw 'Replacement/reparse preparation failure did not preserve the unproven path.'
        }

        $script:ReplacementRoot=Join-Path $probe 'PreMarker'
        $script:ReplacementOriginal=Join-Path $probe 'pre-marker-original'
        $script:ReplacementTarget=Join-Path $probe 'pre-marker-foreign'
        New-Item -ItemType Directory -Path $script:ReplacementTarget | Out-Null
        [IO.File]::WriteAllText((Join-Path $script:ReplacementTarget 'foreign.txt'),'preserve')
        $script:PreparationFailure='replacement-before-marker'
        $preMarkerFailure=$null
        try { New-DayQuayWorkflowProfile $script:ReplacementRoot ([guid]::NewGuid().ToString('N')) | Out-Null }
        catch { $preMarkerFailure=$_.Exception.Message }
        if ($preMarkerFailure -notmatch 'cleanup ownership is unproven.*preserved' -or
            -not (Test-Path -LiteralPath $script:ReplacementRoot) -or
            (Get-Content -LiteralPath (Join-Path $script:ReplacementTarget 'foreign.txt') -Raw) -cne 'preserve') {
            throw 'Pre-marker replacement was not preserved as unproven.'
        }
    } finally {
        Set-Item Function:\Write-NewUtf8Text $actualWriter
        Remove-Variable PreparationFailure,ReplacementRoot,ReplacementOriginal,ReplacementTarget -Scope Script -ErrorAction SilentlyContinue
    }
    Write-Output 'PASS exact profile ownership, guarded partial cleanup and replacement preservation'
} finally {
    Remove-Item -LiteralPath $probe -Recurse -Force
}

# Exercise the production stop/removal adapters together. Once activation has
# returned a PID, an unowned process or failed stop/exit observation preserves
# the profile instead of deleting files beneath an unproven live process.
$script:CleanupScenario=$null
$script:CleanupResult=$null
function Invoke-DayQuayQualificationCore([Collections.IDictionary]$Operations) {
    $state=$Operations.Preflight.Module.SessionState.PSVariable.GetValue('state')
    $state.output=$script:CleanupScenario.directory
    $state.package=Join-Path $state.output 'unsigned.msix'
    [IO.File]::WriteAllText($state.package,'unsigned fixture')
    $state.unsignedPackageSha256=(Get-FileHash $state.package -Algorithm SHA256).Hash.ToLowerInvariant()
    $state.workflowProfile=New-DayQuayWorkflowProfile `
        (Join-Path $state.output 'DayQuay') ([guid]::NewGuid().ToString('N'))
    $state.brokerProcessId=4242
    $state.processOwned=$script:CleanupScenario.process_owned
    $state.processShutdownVerified=$script:CleanupScenario.shutdown_verified
    $state.processHandle=[object]::new()
    $state.process=$script:CleanupScenario.process
    $stopError=$null
    $removeError=$null
    try { & $Operations.StopOwnedProcess | Out-Null } catch { $stopError=$_.Exception.Message }
    try { & $Operations.RemoveWorkflowFixture | Out-Null } catch { $removeError=$_.Exception.Message }
    $cleanupErrors=@(@($stopError,$removeError) | Where-Object { $_ })
    $script:CleanupResult=[ordered]@{
        stop_error=$stopError
        remove_error=$removeError
        profile_exists=Test-Path -LiteralPath $state.workflowProfile.root
        profile_removed=$state.workflowProfileRemoved
    }
    return [pscustomobject]@{
        installation_qualification_passed=$false
        primary_error='controlled cleanup test'
        cleanup_errors=$cleanupErrors
    }
}
$killFailure=[pscustomobject]@{HasExited=$false}
$killFailure | Add-Member ScriptMethod Kill { throw 'controlled kill failure' }
$killFailure | Add-Member ScriptMethod Dispose {}
$observationFailure=[Diagnostics.Process]::new()
try {
    foreach ($scenario in @(
        @{name='activation-unowned';process_owned=$false;process=$null;expected_stop=$false;shutdown_verified=$false;expected_removed=$false},
        @{name='kill-failure';process_owned=$true;process=$killFailure;expected_stop=$true;shutdown_verified=$false;expected_removed=$false},
        @{name='exit-observation-failure';process_owned=$true;process=$observationFailure;expected_stop=$true;shutdown_verified=$false;expected_removed=$false},
        @{name='shutdown-proven';process_owned=$false;process=$null;expected_stop=$false;shutdown_verified=$true;expected_removed=$true}
    )) {
        $directory=Join-Path ([IO.Path]::GetTempPath()) ('dayquay-profile-stop-'+$scenario.name+'-'+[guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $directory | Out-Null
        try {
            $script:CleanupScenario=[ordered]@{
                directory=$directory
                process_owned=$scenario.process_owned
                process=$scenario.process
                shutdown_verified=$scenario.shutdown_verified
            }
            try { Invoke-DayQuayInstallQualification unused unused unused $directory | Out-Null } catch {
                if ($_.Exception.Message -notmatch 'controlled cleanup test') { throw }
            }
            if ($scenario.expected_stop -and -not $script:CleanupResult.stop_error) { throw "$($scenario.name): stop failure was not observed" }
            if ($scenario.expected_removed) {
                if ($script:CleanupResult.remove_error -or $script:CleanupResult.profile_exists -or
                    -not $script:CleanupResult.profile_removed) { throw 'Proven shutdown did not remove the owned workflow profile.' }
            } elseif (-not $script:CleanupResult.remove_error -or
                    $script:CleanupResult.remove_error -notmatch 'shutdown.*unproven.*preserved' -or
                    -not $script:CleanupResult.profile_exists -or $script:CleanupResult.profile_removed) {
                    throw "$($scenario.name): unproven shutdown did not preserve the workflow profile"
            }
            Write-Output "PASS workflow profile shutdown gate: $($scenario.name)"
        } finally {
            Remove-Item -LiteralPath $directory -Recurse -Force
        }
    }
} finally {
    $observationFailure.Dispose()
    Remove-Variable CleanupScenario,CleanupResult -Scope Script -ErrorAction SilentlyContinue
}
