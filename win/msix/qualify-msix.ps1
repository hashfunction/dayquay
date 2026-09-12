# Copyright 2026 Trieflow LLC. MIT. Disposable package qualification only.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if (-not $IsWindows -or $env:CI -ne 'true' -or $PSVersionTable.PSVersion.Major -lt 7) { throw 'Requires disposable Windows CI and PowerShell 7.' }
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '../..'))
function Invoke-Checked([string]$Program,[string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit $LASTEXITCODE" }
}
. (Join-Path $PSScriptRoot 'qualify-msix-install.ps1') -LibraryOnly
$python=Get-DayQuayPackagingPython
$powerShell=(Get-Process -Id $PID).Path
# Fixtures run as separate CI steps before packaging.
$sourceCommit=(git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sourceCommit -cne $env:GITHUB_SHA) { throw 'Source differs from this qualification run.' }
$sdkVersion='10.0.26100.0'
$sdkDirectory=Join-Path ${env:ProgramFiles(x86)} "Windows Kits/10/bin/$sdkVersion/x64"
foreach ($identityMode in @('qualification','store')) {
    $packageOutput=Join-Path $env:RUNNER_TEMP ('dayquay-msix-'+$identityMode+'-'+[guid]::NewGuid().ToString('N'))
    Invoke-Checked $python @('win/msix/msix_qualification.py','--release','dist/Jotmorrow',
        '--artwork','rednotebook/images/jotmorrow-icon/jotmorrow-256.png','--source-root','.','--source-commit',$sourceCommit,
        '--inventory','build-evidence/package-inventory.json','--startup','build-evidence/windows-startup.json',
        '--makeappx',(Join-Path $sdkDirectory 'makeappx.exe'),'--sdk-version',$sdkVersion,'--output',$packageOutput,
        '--identity-mode',$identityMode)
    $recordName=if ($identityMode -eq 'store') {'msix-store-package-record.json'} else {'msix-package-record.json'}
    $packageName=if ($identityMode -eq 'store') {'Jotmorrow_1.0.1.0_x64.msix'} else {'Jotmorrow.Qualification_1.0.1.0_x64.msix'}
    $installationOutput=if ($identityMode -eq 'store') {'build-evidence/msix-store-install'} else {'build-evidence/msix-install'}
    # Each fixed identity repeats the full consumer workflow and owned cleanup.
    [IO.File]::Copy((Join-Path $packageOutput 'package-record.json'),(Join-Path (Get-Location) ('build-evidence/'+$recordName)),$false)
    Invoke-Checked $powerShell @('-NoLogo','-NoProfile','-File','win/msix/qualify-msix-install.ps1',
        '-Package',(Join-Path $packageOutput $packageName),'-PackageRecord',(Join-Path $packageOutput 'package-record.json'),
        '-SignTool',(Join-Path $sdkDirectory 'signtool.exe'),'-Output',$installationOutput,'-IdentityMode',$identityMode)
    if ($identityMode -eq 'store' -and $env:DAYQUAY_EXPORT_STORE_PACKAGE -eq 'true') {
        Invoke-Checked $python @('win/msix/export_store_package.py','--package',(Join-Path $packageOutput $packageName),
            '--source','.', '--output','build-evidence/store-export','--reviewed-public-source',$env:DAYQUAY_REVIEWED_PUBLIC_SOURCE)
    }
}
