$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $IsWindows -or $env:CI -ne 'true') { throw 'Requires an isolated Windows CI runner.' }
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
. (Join-Path $PSScriptRoot 'msix/qualify-msix-install.ps1') -LibraryOnly
$inventoryPath = (Resolve-Path 'build-evidence/package-inventory.json').Path
$inventoryHash = (Get-FileHash $inventoryPath -Algorithm SHA256).Hash.ToLowerInvariant()
$inventory = Get-Content -LiteralPath $inventoryPath -Raw | ConvertFrom-Json
if ($inventory.sourceCommit -cne $env:GITHUB_SHA) { throw 'Stage inventory is not from this source revision.' }
$executable = (Resolve-Path 'dist/Jotmorrow/Jotmorrow.exe').Path
$exeHash = (Get-FileHash $executable -Algorithm SHA256).Hash.ToLowerInvariant()
if ($exeHash -cne $inventory.files.'Jotmorrow.exe'.sha256) { throw 'Native executable differs from stage inventory.' }
$env:APPDATA = Join-Path (Get-Location).Path 'build-evidence/runtime-profile'
if (Test-Path -LiteralPath $env:APPDATA) { throw 'Fresh native startup profile required.' }
New-Item -ItemType Directory $env:APPDATA | Out-Null
$env:DAYQUAY_CI_LOG = Join-Path (Get-Location).Path 'build-evidence/early-startup.txt'
$titleContractPath = Join-Path (Get-Location) 'build-evidence/window-title-contract.json'
Invoke-CheckedNative (Get-DayQuayPackagingPython) @(
  (Join-Path $PSScriptRoot 'msix/window_title_contract.py'), '--source-root', (Get-Location).Path, '--output', $titleContractPath)
$titleContract = Get-Content -LiteralPath $titleContractPath -Raw -Encoding utf8 | ConvertFrom-Json
$expectedTitle = [string]$titleContract.expectedTitle
$process = Start-Process $executable -PassThru
try {
  $deadline = (Get-Date).AddSeconds(45)
  do {
    Start-Sleep -Milliseconds 500
    $process.Refresh()
    if ($process.HasExited) { throw "Jotmorrow exited during startup: $($process.ExitCode)" }
  } until (($process.MainWindowHandle -ne 0 -and (Test-DayQuayWindowTitle $process.MainWindowTitle $expectedTitle)) -or (Get-Date) -gt $deadline)
  if ($process.MainWindowHandle -eq 0 -or -not (Test-DayQuayWindowTitle $process.MainWindowTitle $expectedTitle)) {
    throw "Expected the native Jotmorrow main window, got: $($process.MainWindowTitle)"
  }
  Start-Sleep -Seconds 3
  $process.Refresh()
  if ($process.HasExited -or $process.MainWindowHandle -eq 0 -or -not (Test-DayQuayWindowTitle $process.MainWindowTitle $expectedTitle)) { throw 'Jotmorrow did not retain its exact stable main window.' }
  if ((Get-FileHash $inventoryPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $inventoryHash -or
      (Get-FileHash $executable -Algorithm SHA256).Hash.ToLowerInvariant() -cne $exeHash) { throw 'Native startup inputs changed during observation.' }
  $receipt = @{ source_commit=$env:GITHUB_SHA; workflow_run_id=$env:GITHUB_RUN_ID; workflow_run_attempt=$env:GITHUB_RUN_ATTEMPT; generated_at_utc=[DateTime]::UtcNow.ToString('o'); package_inventory_sha256=$inventoryHash; windows_native_startup=$true; window_title=$process.MainWindowTitle; window_title_contract=$titleContract; executable_sha256=(Get-FileHash $executable -Algorithm SHA256).Hash; interactive_backup_restore_verified=$false; native_source_clearance=$false; msix_built=$false; submitted=$false }
  Write-NewUtf8Json (Join-Path (Get-Location) 'build-evidence/windows-startup.json') $receipt
} finally {
  if (-not $process.HasExited) {
    $process.CloseMainWindow() | Out-Null
    if (-not $process.WaitForExit(5000)) { $process.Kill() }
  }
  Get-ChildItem $env:APPDATA -Recurse -File -Filter '*.log' | ForEach-Object {
    Copy-Item $_.FullName (Join-Path 'build-evidence' ('runtime-' + $_.Name + '.txt'))
  }
  if (Test-Path $env:DAYQUAY_CI_LOG) { Get-Content $env:DAYQUAY_CI_LOG }
}
