# Copyright 2026 Trieflow LLC. MIT. Capture-only native windows and owned cleanup.
. (Join-Path $PSScriptRoot '../msix/qualify-msix-install.ps1') -LibraryOnly
function Add-JotCaptureTypes {
    if ('JotmorrowMarketing.Window' -as [type]) {return}
    Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
namespace JotmorrowMarketing {
 public static class Window {
  [StructLayout(LayoutKind.Sequential)] public struct RECT {public int Left,Top,Right,Bottom;}
  [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr value);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h,IntPtr after,int x,int y,int w,int height,uint flags);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int state);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h,out RECT rect);
  [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetWindowTextW(IntPtr h,StringBuilder text,int count);
  public static string Title(IntPtr h) {var text=new StringBuilder(513);int n=GetWindowTextW(h,text,513);if(n==0||n>=512)throw new InvalidOperationException("Missing or unbounded native caption");return text.ToString();}
 }
}
'@
}
function Assert-JotCaptureProcess($Process,$InstalledRoot,$Record) {
    if ($Process.SafeHandle.IsInvalid -or $Process.SafeHandle.IsClosed -or $Process.HasExited) {throw 'Retained capture process is unavailable.'}
    if ([DayQuayQualification.NativePackageProbe]::GetFullName($Process.Handle) -cne '1659hashfunction.DayQuay_1.0.1.0_x64__r3hxytd7jt6c4' -or
        (Get-CanonicalPath $Process.MainModule.FileName) -ine (Get-CanonicalPath (Join-Path $InstalledRoot 'Jotmorrow.exe'))) {throw 'Capture process package/path differs.'}
    $null=Assert-FileMatchesRecord (Join-Path $InstalledRoot 'Jotmorrow.exe') (Get-RecordPayloadEntry $Record 'Jotmorrow.exe') 'Capture executable'
}
function Get-JotCaptureWindowPlan($Area) {
    if ($Area.Width -lt 1440 -or $Area.Height -lt 900) {throw 'Actual display cannot contain a 1440 by 900 window.'}
    return @{x=[int]($Area.X+($Area.Width-1440)/2);y=[int]($Area.Y+($Area.Height-900)/2);width=1440;height=900}
}
function Set-JotCaptureWindow($State) {
    Add-JotCaptureTypes
    $null=[JotmorrowMarketing.Window]::SetThreadDpiAwarenessContext([IntPtr](-4))
    Add-Type -AssemblyName System.Windows.Forms
    Assert-JotCaptureProcess $State.process $State.installed.InstallLocation $State.record
    $plan=Get-JotCaptureWindowPlan ([Windows.Forms.Screen]::PrimaryScreen.WorkingArea)
    $handle=$State.process.MainWindowHandle
    $null=[JotmorrowMarketing.Window]::ShowWindow($handle,9)
    if (-not [JotmorrowMarketing.Window]::SetWindowPos($handle,[IntPtr]::Zero,$plan.x,$plan.y,$plan.width,$plan.height,0x4040)) {throw 'Native capture resize failed.'}
    $null=[JotmorrowMarketing.Window]::SetForegroundWindow($handle)
    $deadline=[DateTime]::UtcNow.AddSeconds(5)
    do {
        $snapshot=Get-JotCaptureSnapshot $State.process $handle $handle $State.installed.InstallLocation $State.record
        if ($snapshot.main_bounds.width -eq 1440 -and $snapshot.main_bounds.height -eq 900) {break}
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $deadline)
    Assert-JotCaptureSnapshot $snapshot $State.process.Id $handle $handle $State.expectedTitle $State.expectedTitle
    return $snapshot
}
function Get-JotCaptureSnapshot($Process,[int64]$MainHandle,[int64]$TargetHandle,$InstalledRoot,$Record) {
    Assert-JotCaptureProcess $Process $InstalledRoot $Record
    $main=[JotmorrowMarketing.Window+RECT]::new();$target=[JotmorrowMarketing.Window+RECT]::new()
    if (-not [JotmorrowMarketing.Window]::GetWindowRect([IntPtr]$MainHandle,[ref]$main) -or
        -not [JotmorrowMarketing.Window]::GetWindowRect([IntPtr]$TargetHandle,[ref]$target)) {throw 'Native capture bounds unavailable.'}
    [uint32]$mainPid=0;[uint32]$targetPid=0
    $null=[JotmorrowMarketing.Window]::GetWindowThreadProcessId([IntPtr]$MainHandle,[ref]$mainPid)
    $null=[JotmorrowMarketing.Window]::GetWindowThreadProcessId([IntPtr]$TargetHandle,[ref]$targetPid)
    $screen=[Windows.Forms.Screen]::FromHandle([IntPtr]$MainHandle);$area=$screen.WorkingArea
    return [ordered]@{process_id=$Process.Id;main_pid=[int]$mainPid;target_pid=[int]$targetPid;main_handle=$MainHandle;target_handle=$TargetHandle;
        main_title=[JotmorrowMarketing.Window]::Title([IntPtr]$MainHandle);target_title=[JotmorrowMarketing.Window]::Title([IntPtr]$TargetHandle);
        main_visible=[JotmorrowMarketing.Window]::IsWindowVisible([IntPtr]$MainHandle);target_visible=[JotmorrowMarketing.Window]::IsWindowVisible([IntPtr]$TargetHandle);
        foreground_handle=[JotmorrowMarketing.Window]::GetForegroundWindow().ToInt64();dpi=[JotmorrowMarketing.Window]::GetDpiForWindow([IntPtr]$MainHandle);
        display=@{x=$screen.Bounds.X;y=$screen.Bounds.Y;width=$screen.Bounds.Width;height=$screen.Bounds.Height};
        work_area=@{x=$area.X;y=$area.Y;width=$area.Width;height=$area.Height};
        main_bounds=@{x=$main.Left;y=$main.Top;width=($main.Right-$main.Left);height=($main.Bottom-$main.Top)};
        target_bounds=@{x=$target.Left;y=$target.Top;width=($target.Right-$target.Left);height=($target.Bottom-$target.Top)}}
}
function Assert-JotCaptureSnapshot($Snapshot,[int]$ProcessId,[int64]$MainHandle,[int64]$TargetHandle,[string]$MainTitle,[string]$TargetTitle) {
    if ($Snapshot.process_id -ne $ProcessId -or $Snapshot.main_pid -ne $ProcessId -or $Snapshot.target_pid -ne $ProcessId -or
        $Snapshot.main_handle -ne $MainHandle -or $Snapshot.target_handle -ne $TargetHandle -or $Snapshot.foreground_handle -ne $TargetHandle -or
        $Snapshot.main_title -cne $MainTitle -or $Snapshot.target_title -cne $TargetTitle -or -not $Snapshot.main_visible -or -not $Snapshot.target_visible -or $Snapshot.dpi -ne 96) {throw 'Capture is not the exact owned visible foreground surface.'}
    foreach ($bounds in @($Snapshot.main_bounds,$Snapshot.target_bounds,$Snapshot.work_area,$Snapshot.display)) {Assert-DayQuayFiniteRectangle $bounds}
    if ($Snapshot.display.width -lt 1920 -or $Snapshot.display.height -lt 1080 -or $Snapshot.main_bounds.width -ne 1440 -or $Snapshot.main_bounds.height -ne 900) {throw 'Native capture resolution differs.'}
    Assert-DayQuayCaptureBounds $Snapshot.main_bounds $Snapshot.work_area
    # The screenshot is the full main window. A real confirmation dialog may
    # be smaller than the qualification helper's minimum main-window size.
    $target=$Snapshot.target_bounds;$main=$Snapshot.main_bounds
    if ($target.x -lt $main.x -or $target.y -lt $main.y -or
        $target.x+$target.width -gt $main.x+$main.width -or $target.y+$target.height -gt $main.y+$main.height) {throw 'Owned confirmation extends outside the captured main window.'}
}
function Invoke-JotFrameCapture([Collections.IDictionary]$Operations,[int]$ProcessId,[int64]$MainHandle,[int64]$TargetHandle,[string]$MainTitle,[string]$TargetTitle) {
    $before=& $Operations.Observe
    Assert-JotCaptureSnapshot $before $ProcessId $MainHandle $TargetHandle $MainTitle $TargetTitle
    [byte[]]$bytes=& $Operations.Capture $before.main_bounds
    $after=& $Operations.Observe
    Assert-JotCaptureSnapshot $after $ProcessId $MainHandle $TargetHandle $MainTitle $TargetTitle
    if (($before|ConvertTo-Json -Depth 8 -Compress) -cne ($after|ConvertTo-Json -Depth 8 -Compress)) {throw 'Owned window/display changed during native screenshot.'}
    if ($bytes.Length -eq 0 -or $bytes.Length -gt 5000000) {throw 'Native PNG exceeds bounded capture size.'}
    return @{before=$before;after=$after;bytes=$bytes}
}
function Complete-JotCaptureCleanup($State) {
    $operations=[ordered]@{
        driver={if ($State.driver -and -not $State.driver.HasExited) {$State.driver.Kill();if (-not $State.driver.WaitForExit(10000)) {throw 'Owned capture driver remains.'}}}
        process={if ($State.processOwned -and $State.process) {
            if (-not $State.process.HasExited) {$State.process.Kill()}
            $State.cleanupProcessExit=Get-DayQuayProcessExitEvidence $State.process 10000
            if (-not $State.cleanupProcessExit.wait_completed -or $State.cleanupProcessExit.observation_error) {throw 'Retained consumer shutdown is unproven.'}
            $State.processShutdownVerified=$true
        }}
        package={if ($State.installAttempted) {
            $remaining=@(Get-AppxPackage -Name '1659hashfunction.DayQuay' -ErrorAction Stop)
            if ($State.installedByUs -and $State.ownedPackageFullName) {
                $owned=@($remaining|Where-Object {[string]$_.PackageFullName -ceq $State.ownedPackageFullName})
                if ($owned.Count -gt 1) {throw 'Ambiguous registration preserved.'}
                if ($owned.Count -eq 1) {Remove-AppxPackage -Package $State.ownedPackageFullName -ErrorAction Stop}
            }
            $State.residualPackageFullNames=@(Get-AppxPackage -Name '1659hashfunction.DayQuay' -ErrorAction Stop|ForEach-Object PackageFullName)
            if ($State.residualPackageFullNames.Count -or ($State.addCompleted -and -not $State.installedByUs)) {throw 'Unowned or unproven registration state preserved.'}
        }}
        trusted_certificate={if ($State.trustAttempted -and $State.certificate) {
            $path='Cert:\LocalMachine\TrustedPeople\'+$State.certificate.Thumbprint
            if (Test-Path -LiteralPath $path) {Remove-Item -LiteralPath $path -Force -ErrorAction Stop}
            if (Test-Path -LiteralPath $path) {throw 'Owned trusted certificate remains.'}
        }}
        personal_certificate={if ($State.certificate) {
            $path='Cert:\CurrentUser\My\'+$State.certificate.Thumbprint
            if (Test-Path -LiteralPath $path) {Remove-Item -LiteralPath $path -DeleteKey -Force -ErrorAction Stop}
            if (Test-Path -LiteralPath $path) {throw 'Owned personal certificate/key remains.'}
        }}
        profile={if ($State.workflowProfile) {
            if ($State.brokerProcessId -ne 0 -and -not $State.processShutdownVerified) {throw 'Profile preserved because activated process shutdown is unproven.'}
            $State.profileRemoved=Remove-DayQuayWorkflowProfile $State.workflowProfile
        }}
        temporary={if ($State.temporary -and (Test-Path -LiteralPath $State.temporary)) {
            Assert-NoReparsePath $State.temporary
            Remove-Item -LiteralPath $State.temporary -Recurse -Force -ErrorAction Stop
            if (Test-Path -LiteralPath $State.temporary) {throw 'Owned temporary capture files remain.'}
        }}
    }
    foreach ($name in $operations.Keys) {try {& $operations[$name]}catch {$State.cleanupErrors.Add($name+': '+$_.Exception.Message)}}
}
function Get-JotCaptureModules($State) {
    $State.process.Refresh()
    Assert-JotCaptureProcess $State.process $State.installed.InstallLocation $State.record
    $installRoot=Get-CanonicalPath $State.installed.InstallLocation;$windowsRoot=Get-CanonicalPath $env:SystemRoot
    $modules=[Collections.Generic.List[object]]::new();$required=@{}
    foreach ($entry in $State.record.runtime.PSObject.Properties) {$required[[string]$entry.Value]=$false}
    foreach ($module in @($State.process.Modules)) {
        Assert-NoReparsePath $module.FileName;$path=Get-CanonicalPath $module.FileName;$platform=$null
        if (Test-PathInside $path $installRoot) {
            $relative=$path.Substring($installRoot.Length).TrimStart('\','/').Replace('\','/')
            $hash=Assert-FileMatchesRecord $path (Get-RecordPayloadEntry $State.record $relative) $relative
            if ($required.ContainsKey($relative)) {$required[$relative]=$true};$origin='package'
        } elseif (Test-PathInside $path $windowsRoot) {
            $relative=$null;$hash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant();$origin='windows'
        } else {
            $relative=$null;$platform=Get-VerifiedDefenderModuleEvidence $path (Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) 'Microsoft/Windows Defender/Platform')
            $hash=$platform.sha256;$origin='microsoft_defender_signed_platform'
        }
        $modules.Add(@{name=$module.ModuleName;path=$path;relative_path=$relative;sha256=$hash;origin=$origin;platform_signature=$platform})
    }
    foreach ($relative in $required.Keys) {if (-not $required[$relative]) {throw "Capture consumer did not load exact packaged runtime: $relative"}}
    return ,@($modules)
}
