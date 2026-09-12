# Copyright 2026 Trieflow LLC. MIT. Capture the unchanged, already-qualified Store package.
param([Parameter(Mandatory)][string]$Inputs,[Parameter(Mandatory)][string]$QualifiedSource,[Parameter(Mandatory)][string]$CaptureOutput)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'capture_helpers.ps1')
. (Join-Path $PSScriptRoot 'display_modes.ps1')
if (-not $IsWindows -or $env:CI -cne 'true' -or $env:GITHUB_REPOSITORY -cne 'hashfunction/dayquay') {throw 'Requires isolated Jotmorrow Windows CI.'}
Import-Module Appx -UseWindowsPowerShell -ErrorAction Stop
$inputRoot=(Resolve-Path -LiteralPath $Inputs).Path;$qualified=(Resolve-Path -LiteralPath $QualifiedSource).Path
$python=@(Get-Command python -CommandType Application)[0].Source
$powerShell=(Get-Process -Id $PID).Path
Invoke-CheckedNative $python @((Join-Path $PSScriptRoot 'capture_checks.py'),'--inputs',$inputRoot,'--qualified-source',$qualified)
$output=[IO.Path]::GetFullPath($CaptureOutput)
if (Test-Path -LiteralPath $output) {throw 'Capture output exists; replacement refused.'}
New-Item -ItemType Directory -Path $output | Out-Null;Assert-NoReparsePath $output
[IO.File]::Copy((Join-Path $inputRoot 'capture-inputs.json'),(Join-Path $output 'capture-inputs.json'),$false)
$recordPath=Join-Path $inputRoot 'metadata/msix-store-package-record.json'
$record=Get-Content -LiteralPath $recordPath -Raw|ConvertFrom-Json
Assert-DayQuayIdentityRecord $record 'store'
$state=[ordered]@{record=$record;package=(Join-Path $inputRoot 'store/Jotmorrow_1.0.1.0_x64.msix');temporary=$null;certificate=$null;trustAttempted=$false;
    workflowProfile=$null;profileRemoved=$false;installed=$null;installedByUs=$false;installAttempted=$false;addCompleted=$false;ownedPackageFullName=$null;
    process=$null;processOwned=$false;brokerProcessId=0;processShutdownVerified=$false;driver=$null;processExit=$null;cleanupProcessExit=$null;
    expectedTitle=$null;normalClose=$false;uninstallVerified=$false;residualPackageFullNames=@();cleanupErrors=[Collections.Generic.List[string]]::new();
    displayOriginalMode=$null;displayDevice=$null;displayRestoreRequired=$false;displayEvidence=$null;journal=$null}
$expectedHash='47b1b5153eedbbf4709ff8dd143164ff90445009137682722da4951e13b066fe'
$fullName='1659hashfunction.DayQuay_1.0.1.0_x64__r3hxytd7jt6c4'
$primary=$null;$unsignedUnchanged=$false
try {
    foreach ($profile in @((Join-Path $env:APPDATA 'DayQuay'),(Join-Path $env:USERPROFILE '.rednotebook'))) {
        if (Test-Path -LiteralPath $profile) {throw 'Existing current or legacy journal profile must be preserved.'}
    }
    if (@(Get-AppxPackage -Name '1659hashfunction.DayQuay' -ErrorAction Stop).Count) {throw 'Existing Jotmorrow registration preserved.'}
    Start-MarketingDisplay $state
    $temporary=Join-Path $env:RUNNER_TEMP ('.jotmorrow-capture-'+[guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temporary | Out-Null;$state.temporary=$temporary
    $state.workflowProfile=New-DayQuayWorkflowProfile (Join-Path $env:APPDATA 'DayQuay') ([guid]::NewGuid().ToString('N'))
    # Ordinary documented application preferences in the exclusive fictional profile.
    [IO.File]::WriteAllText((Join-Path $state.workflowProfile.root 'configuration.cfg'),"firstStart=0`nmainFont=Segoe UI 14`nmainFrameWidth=1440`nmainFrameHeight=900`nleftDividerPosition=300`nautoIndent=0`n",[Text.UTF8Encoding]::new($false))
    $titlePath=Join-Path $temporary 'current-title.json'
    Invoke-CheckedNative $python @((Join-Path $qualified 'win/msix/window_title_contract.py'),'--source-root',$qualified,'--output',$titlePath)
    $state.expectedTitle=[string](Get-Content -LiteralPath $titlePath -Raw|ConvertFrom-Json).expectedTitle
    [IO.File]::Copy($titlePath,(Join-Path $output 'capture-title.json'),$false)
    $signTool=Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10/bin/10.0.26100.0/x64/signtool.exe'
    $toolHash=(Get-FileHash -LiteralPath $signTool -Algorithm SHA256).Hash
    $signed=Join-Path $temporary 'Jotmorrow.capture.signed.msix'
    [IO.File]::Copy($state.package,$signed,$false)
    $state.certificate=New-SelfSignedCertificate -Type Custom -KeyUsage DigitalSignature -KeyExportPolicy NonExportable -KeySpec Signature `
        -CertStoreLocation 'Cert:\CurrentUser\My' -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3','2.5.29.19={text}') `
        -Subject 'CN=B6A2631A-FD32-45CC-AE12-82466975F528' -FriendlyName 'Jotmorrow ephemeral marketing capture' -NotAfter (Get-Date).AddHours(2)
    $public=Join-Path $temporary 'capture-public.cer'
    Export-Certificate -Cert $state.certificate -FilePath $public | Out-Null
    $state.trustAttempted=$true;Import-Certificate -FilePath $public -CertStoreLocation 'Cert:\LocalMachine\TrustedPeople' | Out-Null
    Invoke-CheckedNative $signTool @('sign','/fd','SHA256','/sha1',$state.certificate.Thumbprint,'/s','My',$signed)
    Invoke-CheckedNative $signTool @('verify','/pa','/all','/v',$signed)
    $signature=Get-AuthenticodeSignature -LiteralPath $signed
    if ($signature.Status -ne [Management.Automation.SignatureStatus]::Valid -or $signature.SignerCertificate.Thumbprint -cne $state.certificate.Thumbprint -or
        (Get-FileHash -LiteralPath $signTool -Algorithm SHA256).Hash -cne $toolHash -or
        (Get-FileHash -LiteralPath $state.package -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expectedHash) {throw 'Capture signing source/tool/certificate integrity differs.'}
    $state.installAttempted=$true
    Add-AppxPackage -Path $signed -ErrorAction Stop;$state.addCompleted=$true
    $matches=@(Get-AppxPackage -Name '1659hashfunction.DayQuay' -ErrorAction Stop)
    if ($matches.Count -ne 1 -or $matches[0].PackageFullName -cne $fullName -or
        $matches[0].Publisher -cne 'CN=B6A2631A-FD32-45CC-AE12-82466975F528' -or
        $matches[0].PackageFamilyName -cne '1659hashfunction.DayQuay_r3hxytd7jt6c4') {throw 'Installed capture registration differs; ownership unproven.'}
    $state.installed=$matches[0];$state.installedByUs=$true;$state.ownedPackageFullName=$fullName
    foreach ($row in $record.payload.PSObject.Properties) {$null=Assert-FileMatchesRecord (Join-Path $state.installed.InstallLocation $row.Name) $row.Value $row.Name}
    Add-DayQuayActivationTypes
    $state.brokerProcessId=[int][DayQuayQualification.ActivationBroker]::Activate('1659hashfunction.DayQuay_r3hxytd7jt6c4!DayQuay')
    $state.process=[Diagnostics.Process]::GetProcessById($state.brokerProcessId);$null=$state.process.SafeHandle
    Assert-JotCaptureProcess $state.process $state.installed.InstallLocation $record;$state.processOwned=$true
    $deadline=[DateTime]::UtcNow.AddSeconds(30)
    do {$state.process.Refresh();if($state.process.HasExited){throw 'Capture consumer exited during startup.'};Start-Sleep -Milliseconds 200}
    until (($state.process.MainWindowHandle -ne 0 -and $state.process.MainWindowTitle -ceq $state.expectedTitle) -or [DateTime]::UtcNow -ge $deadline)
    if ($state.process.MainWindowHandle -eq 0 -or $state.process.MainWindowTitle -cne $state.expectedTitle) {throw ('Actual current-date journal title differs: '+$state.process.MainWindowTitle)}
    Write-NewUtf8Json (Join-Path $output 'loaded-modules.json') (Get-JotCaptureModules $state)
    Write-NewUtf8Json (Join-Path $output 'native-window.json') (Set-JotCaptureWindow $state)
    $archive=Join-Path $temporary 'Autumn-journal.zip'
    $info=[Diagnostics.ProcessStartInfo]::new();$info.FileName=$python;$info.UseShellExecute=$false
    $info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
    foreach ($arg in @((Join-Path $PSScriptRoot 'capture_ui.py'),'--qualified-source',$qualified,'--process-id',[string]$state.process.Id,
        '--main-window-handle',[string]$state.process.MainWindowHandle.ToInt64(),'--initial-title',$state.expectedTitle,
        '--profile-root',$state.workflowProfile.root,'--archive',$archive,'--record',$recordPath,'--output',$output,'--powershell',$powerShell)) {$info.ArgumentList.Add($arg)}
    $state.driver=[Diagnostics.Process]::Start($info);$null=$state.driver.SafeHandle
    $stdout=$state.driver.StandardOutput.ReadToEndAsync();$stderr=$state.driver.StandardError.ReadToEndAsync()
    if (-not $state.driver.WaitForExit(180000)) {throw 'Bounded native journal capture timed out.'}
    $driverOutput=$stdout.GetAwaiter().GetResult();$driverError=$stderr.GetAwaiter().GetResult()
    if ($state.driver.ExitCode -ne 0) {throw ('Native journal capture failed: '+$driverError)}
    $state.journal=Get-Content -LiteralPath (Join-Path $output 'journal-capture.json') -Raw|ConvertFrom-Json
    if ($state.journal.process_id -ne $state.process.Id -or $state.journal.consumer_acceptance -ne $false -or
        ($state.journal.captures -join ',') -cne '01-journal-entry,02-restore-preview,03-restored-journal') {throw 'Capture result process/stages differ.'}
    foreach ($name in @('01-journal-entry','02-restore-preview','03-restored-journal')) {
        $frame=Get-Content -LiteralPath (Join-Path $output ($name+'.json')) -Raw|ConvertFrom-Json
        if ($frame.process_id -ne $state.process.Id -or $frame.qualified_source_commit -cne $record.sourceCommit -or
            $frame.package_full_name -cne $state.ownedPackageFullName -or $frame.pixel_manipulation -ne $false) {throw 'Native screenshot receipt identity differs.'}
        $null=Assert-FileMatchesRecord (Join-Path $output ($name+'.png')) $frame.png 'Unaltered native screenshot'
    }
    Write-NewUtf8Json (Join-Path $output 'loaded-modules-after-capture.json') (Get-JotCaptureModules $state)
    Assert-JotCaptureProcess $state.process $state.installed.InstallLocation $record
    if (-not $state.process.CloseMainWindow()) {throw 'Captured journal refused normal close.'}
    $state.processExit=Get-DayQuayProcessExitEvidence $state.process 15000
    if (-not $state.processExit.normal_exit) {throw 'Captured journal did not close normally with zero exit.'}
    $state.normalClose=$true;$state.processShutdownVerified=$true
    Remove-AppxPackage -Package $state.ownedPackageFullName -ErrorAction Stop
    if (@(Get-AppxPackage -Name '1659hashfunction.DayQuay' -ErrorAction Stop).Count) {throw 'Registration remains after normal uninstall.'}
    $state.uninstallVerified=$true
} catch {$primary=$_.Exception.Message}
finally {
    Complete-JotCaptureCleanup $state
    try {Restore-MarketingDisplay $state}catch {$state.cleanupErrors.Add('display: '+$_.Exception.Message)}
    if ($state.displayEvidence) {Write-NewUtf8Json (Join-Path $output 'native-display.json') $state.displayEvidence}
    try {$unsignedUnchanged=(Get-FileHash -LiteralPath $state.package -Algorithm SHA256).Hash.ToLowerInvariant() -ceq $expectedHash}catch {$state.cleanupErrors.Add('Original unsigned package cannot be rechecked.')}
    $captured=(-not $primary -and $state.cleanupErrors.Count -eq 0 -and $state.normalClose -and $state.uninstallVerified -and $state.profileRemoved -and $unsignedUnchanged)
    Write-NewUtf8Json (Join-Path $output 'capture-result.json') @{schema_version=1;purpose='real native marketing screenshots only';captured=$captured;
        consumer_acceptance=$false;installation_qualification_claimed=$false;product_binary_changed=$false;submission_changed=$false;
        capture_source_commit=$env:GITHUB_SHA;capture_run_id=$env:GITHUB_RUN_ID;capture_run_attempt=$env:GITHUB_RUN_ATTEMPT;
        qualified_source_commit='64e8174c5f375fecf45539594b6a6b4beac8e025';qualified_run_id='34681664116';original_unsigned_sha256=$expectedHash;
        original_unsigned_unchanged=$unsignedUnchanged;certificate_private_key_exported=$false;package_full_name=$state.ownedPackageFullName;
        normal_close_verified=$state.normalClose;process_exit=$state.processExit;cleanup_process_exit=$state.cleanupProcessExit;uninstall_verified=$state.uninstallVerified;
        workflow_profile_removed=$state.profileRemoved;residual_package_full_names=$state.residualPackageFullNames;primary_error=$primary;cleanup_errors=@($state.cleanupErrors);
        captured_at_utc=[DateTime]::UtcNow.ToString('o')}
    foreach ($process in @($state.driver,$state.process)) {if($process){$process.Dispose()}}
}
if (-not $captured) {throw "Native marketing capture incomplete: $primary; cleanup: $($state.cleanupErrors -join '; ')"}
Write-Output 'Captured three real Jotmorrow screens and completed normal close/uninstall/owned profile cleanup. Capture only.'
