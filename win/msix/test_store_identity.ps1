# Copyright 2026 Trieflow LLC. MIT. Fixed identity boundaries before installation.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'qualify-msix-install.ps1') -LibraryOnly
foreach ($mode in @('qualification','store')) {
    $identity=Get-DayQuayExpectedIdentity $mode
    $expectedName=if ($mode -eq 'store') {'1659hashfunction.DayQuay'} else {'Trieflow.Jotmorrow.Qualification'}
    if ($identity.packageName -cne $expectedName) {throw 'Wrong exact package name'}
    if ($identity.applicationId -cne 'DayQuay' -or $identity.executable -cne 'Jotmorrow.exe' -or $identity.version -cne '1.0.1.0') {throw 'Rename changed fixed application identity or wrong executable/version'}
    if ($mode -eq 'store' -and $identity.publisher -cne 'CN=B6A2631A-FD32-45CC-AE12-82466975F528') {throw 'Wrong Store publisher'}
    $record=[pscustomobject]@{schemaVersion=1;identityMode=$mode;qualificationIdentityOnly=($mode -eq 'qualification');storeIdentityUsed=($mode -eq 'store');identity=[pscustomobject]$identity;signed=$false;publicRelease=$false;licenseClearanceClaimed=$false;installationQualificationPassed=$false}
    Assert-DayQuayIdentityRecord $record $mode
    foreach ($field in @('identityMode','qualificationIdentityOnly','storeIdentityUsed','signed','publicRelease','licenseClearanceClaimed','installationQualificationPassed','packageName','publisher','capability')) {
        $changed= $record | ConvertTo-Json -Depth 10 | ConvertFrom-Json
        if ($field -in @('packageName','publisher','capability')) {$changed.identity.$field='foreign'}
        elseif ($field -eq 'identityMode') {$changed.$field=if ($mode -eq 'store') {'qualification'} else {'store'}}
        else {$changed.$field=-not $changed.$field}
        $rejected=$false
        try {Assert-DayQuayIdentityRecord $changed $mode} catch {$rejected=$true}
        if (-not $rejected) {throw "Accepted changed $mode identity record: $field"}
    }
    $opposite=if ($mode -eq 'store') {'qualification'} else {'store'}
    $rejected=$false;try {Assert-DayQuayIdentityRecord $record $opposite} catch {$rejected=$true}
    if (-not $rejected) {throw 'Accepted opposite caller identity mode'}
}
$rejected=$false;try {Get-DayQuayExpectedIdentity 'foreign'} catch {$rejected=$true}
if (-not $rejected) {throw 'Accepted arbitrary identity mode'}
Write-Output 'PASS: both fixed identities, 20 changed metadata cases, two cross-mode records and arbitrary-mode refusal.'
