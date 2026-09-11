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
$packageOutput=Join-Path $env:RUNNER_TEMP ('dayquay-msix-'+[guid]::NewGuid().ToString('N'))
Invoke-Checked $python @('win/msix/msix_qualification.py','--release','dist/DayQuay',
    '--artwork','rednotebook/images/dayquay-icon/dayquay-256.png','--source-root','.','--source-commit',$sourceCommit,
    '--inventory','build-evidence/package-inventory.json','--startup','build-evidence/windows-startup.json',
    '--makeappx',(Join-Path $sdkDirectory 'makeappx.exe'),'--sdk-version',$sdkVersion,'--output',$packageOutput)
# Upload only the metadata copy. Unsigned/signed MSIX and certificates never enter artifact globs.
[IO.File]::Copy((Join-Path $packageOutput 'package-record.json'),(Join-Path (Get-Location) 'build-evidence/msix-package-record.json'),$false)
Invoke-Checked $powerShell @('-NoLogo','-NoProfile','-File','win/msix/qualify-msix-install.ps1',
    '-Package',(Join-Path $packageOutput 'DayQuay.Qualification_1.0.0.0_x64.msix'),
    '-PackageRecord',(Join-Path $packageOutput 'package-record.json'),
    '-SignTool',(Join-Path $sdkDirectory 'signtool.exe'),'-Output','build-evidence/msix-install')
