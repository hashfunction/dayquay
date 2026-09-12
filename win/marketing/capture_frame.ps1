# Copyright 2026 Trieflow LLC. MIT. Original native pixels only.
param([int]$ProcessId,[int64]$MainWindowHandle,[int64]$TargetWindowHandle,[string]$MainTitle,[string]$TargetTitle,[string]$Record,[string]$OutputStem)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'capture_helpers.ps1')
if (-not $IsWindows -or $env:CI -cne 'true') {throw 'Native capture requires isolated Windows CI.'}
Add-DayQuayActivationTypes;Add-JotCaptureTypes
Add-Type -AssemblyName System.Drawing;Add-Type -AssemblyName System.Windows.Forms
$null=[JotmorrowMarketing.Window]::SetThreadDpiAwarenessContext([IntPtr](-4))
$recordValue=Get-Content -LiteralPath $Record -Raw|ConvertFrom-Json
Assert-DayQuayIdentityRecord $recordValue 'store'
$installed=@(Get-AppxPackage -Name '1659hashfunction.DayQuay' -ErrorAction Stop)
if ($installed.Count -ne 1 -or $installed[0].PackageFullName -cne '1659hashfunction.DayQuay_1.0.1.0_x64__r3hxytd7jt6c4') {throw 'Exact installed capture registration differs.'}
$process=[Diagnostics.Process]::GetProcessById($ProcessId)
$null=$process.SafeHandle
try {
    $ops=@{
        Observe={Get-JotCaptureSnapshot $process $MainWindowHandle $TargetWindowHandle $installed[0].InstallLocation $recordValue}
        Capture={param($bounds)
            $bitmap=[Drawing.Bitmap]::new(1440,900);$graphics=[Drawing.Graphics]::FromImage($bitmap);$memory=[IO.MemoryStream]::new()
            try {$graphics.CopyFromScreen([int]$bounds.x,[int]$bounds.y,0,0,$bitmap.Size);$bitmap.Save($memory,[Drawing.Imaging.ImageFormat]::Png);return ,$memory.ToArray()}
            finally {$memory.Dispose();$graphics.Dispose();$bitmap.Dispose()}
        }
    }
    $result=Invoke-JotFrameCapture $ops $ProcessId $MainWindowHandle $TargetWindowHandle $MainTitle $TargetTitle
    foreach ($extension in @('.png','.json')) {if (Test-Path -LiteralPath ($OutputStem+$extension)) {throw 'Capture output exists; refused replacement.'}}
    $file=[IO.File]::Open(($OutputStem+'.png'),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try {$file.Write($result.bytes,0,$result.bytes.Length);$file.Flush($true)}finally{$file.Dispose()}
    Write-NewUtf8Json ($OutputStem+'.json') @{schema_version=1;purpose='unaltered native marketing screenshot';consumer_acceptance=$false;
        process_id=$ProcessId;qualified_source_commit=$recordValue.sourceCommit;package_full_name=$installed[0].PackageFullName;
        before=$result.before;after=$result.after;png=@{bytes=$result.bytes.Length;sha256=(Get-FileHash -LiteralPath ($OutputStem+'.png') -Algorithm SHA256).Hash.ToLowerInvariant()};
        pixel_manipulation=$false;captured_at_utc=[DateTime]::UtcNow.ToString('o')}
} finally {$process.Dispose()}
