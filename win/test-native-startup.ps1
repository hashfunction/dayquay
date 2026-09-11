$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $IsWindows -or $env:CI -ne 'true') { throw 'Requires an isolated Windows CI runner.' }
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))
$executable = (Resolve-Path 'dist/DayQuay/DayQuay.exe').Path
$process = Start-Process $executable -PassThru
try {
  $deadline = (Get-Date).AddSeconds(45)
  do {
    Start-Sleep -Milliseconds 500
    $process.Refresh()
    if ($process.HasExited) { throw "DayQuay exited during startup: $($process.ExitCode)" }
  } until ($process.MainWindowHandle -ne 0 -or (Get-Date) -gt $deadline)
  if ($process.MainWindowHandle -eq 0) { throw 'DayQuay did not create a native main window.' }
  @{ source_commit=$env:GITHUB_SHA; generated_at_utc=[DateTime]::UtcNow.ToString('o'); windows_native_startup=$true; window_title=$process.MainWindowTitle; executable_sha256=(Get-FileHash $executable -Algorithm SHA256).Hash; interactive_backup_restore_verified=$false; native_source_clearance=$false; msix_built=$false; submitted=$false } | ConvertTo-Json | Set-Content build-evidence/windows-startup.json -Encoding utf8NoBOM
} finally {
  if (-not $process.HasExited) {
    $process.CloseMainWindow() | Out-Null
    if (-not $process.WaitForExit(5000)) { $process.Kill() }
  }
}
