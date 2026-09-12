# Disposable Windows CI installation qualification for DayQuay.
# Copyright 2026 Trieflow LLC. MIT licensed.
# Installation-flow structure adapted from ReticleQuay's MIT helper; the full
# retained notice is in RETICLEQUAY-MIT.txt.
[CmdletBinding()]
param(
    [Parameter()][string]$Package,
    [Parameter()][string]$PackageRecord,
    [Parameter()][string]$SignTool,
    [Parameter()][string]$Output,
    [Parameter()][switch]$LibraryOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-DayQuayQualificationCore([Collections.IDictionary]$Operations) {
    $required = @(
        'Preflight','PrepareSignedCopy','PrepareWorkflowFixture','Install','ActivateAndVerify','CloseCleanly','UninstallAndVerify',
        'StopOwnedProcess','RemoveOwnedPackage','RemoveTrustedCertificate','RemovePersonalCertificate','RemoveWorkflowFixture','RemoveTemporaryFiles'
    )
    foreach ($name in $required) {
        if (-not $Operations.Contains($name) -or $Operations[$name] -isnot [scriptblock]) {
            throw "Missing qualification operation: $name"
        }
    }
    $primaryError = $null
    $cleanupErrors = [Collections.Generic.List[string]]::new()
    try {
        foreach ($name in @('Preflight','PrepareSignedCopy','PrepareWorkflowFixture','Install','ActivateAndVerify','CloseCleanly','UninstallAndVerify')) {
            # Native tools such as SignTool emit stdout. Keep it in the host
            # log without turning this function's structured result into an array.
            & $Operations[$name] | Out-Host
        }
    } catch {
        $primaryError = $_.Exception.Message
    } finally {
        foreach ($name in @('StopOwnedProcess','RemoveOwnedPackage','RemoveTrustedCertificate','RemovePersonalCertificate','RemoveWorkflowFixture','RemoveTemporaryFiles')) {
            try {
                & $Operations[$name] | Out-Host
            } catch {
                $cleanupErrors.Add("${name}: $($_.Exception.Message)")
            }
        }
    }
    return [pscustomobject][ordered]@{
        installation_qualification_passed = (-not $primaryError -and $cleanupErrors.Count -eq 0)
        primary_error = $primaryError
        cleanup_errors = @($cleanupErrors)
    }
}

function Invoke-CheckedNative([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit $LASTEXITCODE" }
}

function Get-DayQuayProcessExitEvidence([Diagnostics.Process]$Process, [int]$TimeoutMilliseconds) {
    # Adapted from FileQuay 39f6fadb: getters can otherwise conceal observation errors.
    $evidence = [ordered]@{ process_id=$null; wait_completed=$false; exit_code=$null; normal_exit=$false; observation_error=$null }
    try {
        $evidence.process_id = $Process.get_Id()
        $evidence.wait_completed = $Process.WaitForExit($TimeoutMilliseconds)
        if ($evidence.wait_completed) {
            $evidence.exit_code = $Process.get_ExitCode()
            $evidence.normal_exit = $evidence.exit_code -eq 0
        }
    } catch { $evidence.observation_error = $_.Exception.ToString() }
    return [pscustomobject]$evidence
}

function Assert-NoReparsePath([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    while ($item) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point in qualified path: $($item.FullName)" }
        $item = if ($item -is [IO.DirectoryInfo]) { $item.Parent } else { $item.Directory }
    }
}

function Get-CanonicalPath([string]$Path) {
    return [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
}

function Test-PathInside([string]$Candidate, [string]$Root) {
    $candidatePath = Get-CanonicalPath $Candidate
    $rootPath = Get-CanonicalPath $Root
    return $candidatePath.Equals($rootPath, [StringComparison]::OrdinalIgnoreCase) -or
        $candidatePath.StartsWith($rootPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
}

function Get-RecordPayloadEntry([object]$Record, [string]$Relative) {
    $property = $Record.payload.PSObject.Properties[$Relative]
    if (-not $property) { throw "Installed/package module is absent from the verified payload record: $Relative" }
    return $property.Value
}

function Get-VerifiedDefenderModuleEvidence([string]$Path, [string]$PlatformRoot) {
    # Windows run 34604065415 loaded Defender's signed AMSI module outside SystemRoot.
    # Restrict this exception to the observed module in the documented platform layout.
    $path = Get-CanonicalPath $Path
    $platform = Get-CanonicalPath $PlatformRoot
    if (-not (Test-PathInside $path $platform)) { throw 'Defender module is outside its platform root.' }
    $relative = [IO.Path]::GetRelativePath($platform, $path).Replace('\','/')
    if ($relative -cnotmatch '^\d+\.\d+\.\d+\.\d+-\d+/MpOav\.dll$') { throw 'Unexpected Defender module or platform path.' }
    Assert-NoReparsePath $path
    $item = Get-Item -LiteralPath $path -Force
    if ($item.PSIsContainer -or $item.LinkType) { throw 'Defender module is not a regular non-link file.' }
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    $signature = Get-AuthenticodeSignature -LiteralPath $path
    $certificate = $signature.SignerCertificate
    if ([string]$signature.Status -cne 'Valid' -or -not $certificate) {
        throw 'Defender module lacks a valid Microsoft Authenticode signature.'
    }
    $commonNames = [Collections.Generic.List[string]]::new()
    $organizations = [Collections.Generic.List[string]]::new()
    foreach ($rdn in $certificate.SubjectName.EnumerateRelativeDistinguishedNames()) {
        if ($rdn.HasMultipleElements) { throw 'Ambiguous multi-valued Defender signer RDN.' }
        switch ($rdn.GetSingleElementType().Value) {
            '2.5.4.3' { $commonNames.Add($rdn.GetSingleElementValue()) }
            '2.5.4.10' { $organizations.Add($rdn.GetSingleElementValue()) }
        }
    }
    if ($commonNames.Count -ne 1 -or $organizations.Count -ne 1 -or
        $commonNames[0] -cnotin @('Microsoft Windows Publisher','Microsoft Corporation','Microsoft Windows') -or
        $organizations[0] -cne 'Microsoft Corporation') {
        throw ('Defender signature does not identify the required Microsoft signer. Parsed certificate: ' +
            (@{common_names=@($commonNames);organizations=@($organizations);subject=$certificate.Subject;
                issuer=$certificate.Issuer;thumbprint=$certificate.Thumbprint;status=[string]$signature.Status} | ConvertTo-Json -Compress))
    }
    Assert-NoReparsePath $path
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $hash) { throw 'Defender module changed during signature verification.' }
    return [ordered]@{ sha256=$hash; signature_status=[string]$signature.Status;
        signer_subject=$certificate.Subject; signer_issuer=$certificate.Issuer; signer_thumbprint=$certificate.Thumbprint;
        signer_common_name=$commonNames[0]; signer_organization=$organizations[0] }
}

function Assert-FileMatchesRecord([string]$Path, [object]$Expected, [string]$Label) {
    Assert-NoReparsePath $Path
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer -or $item.LinkType) { throw "$Label is not a regular non-link file: $Path" }
    if ($item.Length -ne [int64]$Expected.bytes) { throw "$Label size differs from package record: $Path" }
    $hash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne ([string]$Expected.sha256).ToLowerInvariant()) { throw "$Label hash differs from package record: $Path" }
    return $hash
}

function Add-DayQuayActivationTypes {
    if ('DayQuayQualification.NativePackageProbe' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;

namespace DayQuayQualification {
    [ComImport, Guid("45BA127D-10A8-46EA-8AB7-56EA9078943C")]
    internal class ApplicationActivationManagerClass { }

    [ComImport, Guid("2E941141-7F97-4756-BA1D-9DECDE894A3D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IApplicationActivationManager {
        [PreserveSig]
        int ActivateApplication([MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            [MarshalAs(UnmanagedType.LPWStr)] string arguments, uint options, out uint processId);
        [PreserveSig]
        int ActivateForFile([MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            IntPtr shellItemArray, [MarshalAs(UnmanagedType.LPWStr)] string verb, out uint processId);
        [PreserveSig]
        int ActivateForProtocol([MarshalAs(UnmanagedType.LPWStr)] string appUserModelId,
            IntPtr shellItemArray, out uint processId);
    }

    public static class ActivationBroker {
        public static uint Activate(string appUserModelId) {
            var manager = (IApplicationActivationManager)new ApplicationActivationManagerClass();
            uint processId;
            int result = manager.ActivateApplication(appUserModelId, null, 0, out processId);
            if (result < 0) Marshal.ThrowExceptionForHR(result);
            if (processId == 0) throw new InvalidOperationException("Activation broker returned process ID zero.");
            return processId;
        }
    }

    public static class NativePackageProbe {
        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr window);
        [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr window, int command);
        [DllImport("user32.dll", SetLastError=true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool SetWindowPos(IntPtr window, IntPtr after, int x, int y, int width, int height, uint flags);
        [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
        private const int ERROR_SUCCESS = 0;
        private const int ERROR_INSUFFICIENT_BUFFER = 122;
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode)]
        private static extern int GetPackageFullName(IntPtr process, ref uint length, StringBuilder packageFullName);

        public static string GetFullName(IntPtr process) {
            uint length = 0;
            int first = GetPackageFullName(process, ref length, null);
            if (first != ERROR_INSUFFICIENT_BUFFER || length == 0)
                throw new InvalidOperationException("Initial GetPackageFullName returned " + first + ", expected 122.");
            var value = new StringBuilder((int)length);
            int second = GetPackageFullName(process, ref length, value);
            if (second != ERROR_SUCCESS)
                throw new InvalidOperationException("Second GetPackageFullName returned " + second + ", expected 0.");
            return value.ToString();
        }
    }
}
'@
}

function Test-DayQuayWindowTitle([string]$Title, [string]$ExpectedTitle) {
    if (-not $ExpectedTitle -or $ExpectedTitle.Length -gt 512 -or $ExpectedTitle.Contains("`n") -or $ExpectedTitle.Contains("`r")) { return $false }
    return $Title -ceq $ExpectedTitle
}

function Assert-DayQuayFiniteRectangle($Rectangle) {
    foreach ($key in @('x','y','width','height')) {
        if ($null -eq $Rectangle.$key -or -not [double]::IsFinite([double]$Rectangle.$key) -or
            [Math]::Abs([double]$Rectangle.$key) -gt 100000) { throw 'Invalid or unbounded window/desktop geometry.' }
    }
    if ($Rectangle.width -le 0 -or $Rectangle.height -le 0) { throw 'Empty window/desktop geometry.' }
}

function Assert-DayQuayCaptureBounds($Bounds, $WorkArea) {
    Assert-DayQuayFiniteRectangle $Bounds
    Assert-DayQuayFiniteRectangle $WorkArea
    if ($Bounds.width -lt 400 -or $Bounds.height -lt 300 -or $Bounds.width -gt 8192 -or $Bounds.height -gt 8192 -or
        $Bounds.x -lt $WorkArea.x -or $Bounds.y -lt $WorkArea.y -or
        ($Bounds.x + $Bounds.width) -gt ($WorkArea.x + $WorkArea.width) -or
        ($Bounds.y + $Bounds.height) -gt ($WorkArea.y + $WorkArea.height)) {
        throw 'Whole owned window does not fit the observed monitor work area.'
    }
}

function Set-DayQuayCapturePlacement([int]$ProcessId, [string]$ExpectedTitle, [Collections.IDictionary]$Operations, [Collections.IDictionary]$Evidence) {
    $Evidence.adjusted=$false
    $Evidence.before=$null
    $Evidence.after=$null
    $Evidence.requested=$null
    for ($attempt=0; $attempt -lt 20; $attempt++) {
        $observed=& $Operations.Observe
        if ($null -eq $Evidence.before) { $Evidence.before=$observed }
        $Evidence.after=$observed
        if ($observed.process_id -ne $ProcessId -or -not (Test-DayQuayWindowTitle $observed.title $ExpectedTitle) -or -not $observed.visible) {
            throw 'Capture placement observation is not the exact visible owned window.'
        }
        Assert-DayQuayFiniteRectangle $observed.bounds
        Assert-DayQuayFiniteRectangle $observed.work_area
        if ($observed.bounds.width -lt 400 -or $observed.bounds.height -lt 300 -or
            $observed.bounds.width -gt 8192 -or $observed.bounds.height -gt 8192 -or
            $observed.work_area.width -lt 432 -or $observed.work_area.height -lt 332) {
            throw 'Window or desktop cannot support the required complete screenshot.'
        }
        $fits=$false
        try { Assert-DayQuayCaptureBounds $observed.bounds $observed.work_area; $fits=$true } catch { }
        if ($fits) { return }
        if (-not $Evidence.adjusted) {
            # Keep a margin for native window borders. Never crop the screenshot
            # or replace observed dimensions with the requested dimensions.
            $width=[int][Math]::Floor([Math]::Min($observed.bounds.width,$observed.work_area.width-32))
            $height=[int][Math]::Floor([Math]::Min($observed.bounds.height,$observed.work_area.height-32))
            $requested=@{x=[int][Math]::Floor($observed.work_area.x+($observed.work_area.width-$width)/2);
                y=[int][Math]::Floor($observed.work_area.y+($observed.work_area.height-$height)/2);width=$width;height=$height}
            $Evidence.requested=$requested
            & $Operations.Move $requested | Out-Null
            $Evidence.adjusted=$true
        }
        & $Operations.Wait | Out-Null
    }
    throw 'Owned window did not fit after the bounded native move/resize.'
}

function Assert-DayQuayWindowEvidence($Snapshot, [string]$ExpectedTitle) {
    if (-not (Test-DayQuayWindowTitle $Snapshot.title $ExpectedTitle) -or $Snapshot.expected_title -cne $ExpectedTitle -or -not $Snapshot.visible -or $Snapshot.process_id -le 0 -or
        $Snapshot.width -lt 400 -or $Snapshot.height -lt 300 -or $Snapshot.width -gt 8192 -or $Snapshot.height -gt 8192 -or
        -not $Snapshot.screenshot_captured -or $Snapshot.screenshot_sha256 -cnotmatch '^[0-9a-f]{64}$' -or
        $Snapshot.sampled_colors -lt 16) { throw 'Missing exact rendered DayQuay window/screenshot evidence.' }
    if ($Snapshot.accessibility_scope -cne 'GTK startup only; journal/backup/restore workflows untested') {
        throw 'GTK startup evidence must retain its explicit workflow limitation.'
    }
    $actionable = @($Snapshot.controls | Where-Object {
        $_.enabled -and -not $_.offscreen -and $_.process_id -eq $Snapshot.process_id -and $_.name -and
        $_.control_type -match 'ControlType\.(Button|MenuItem|Edit|ComboBox|ListItem)'
    }).Count
    if ($Snapshot.startup_limited -ne ($actionable -eq 0) -or
        $Snapshot.actionable_controls_verified -ne ($actionable -gt 0)) { throw 'GTK accessibility claims differ from observed controls.' }
    if (@($Snapshot.top_level_windows | Where-Object { -not $_.offscreen -and -not (Test-DayQuayWindowTitle $_.name $ExpectedTitle) }).Count) {
        throw 'Unexpected additional top-level surface in the owned DayQuay process.'
    }
}

function Get-DayQuayPackagingPython {
    $recordPath = Join-Path $PSScriptRoot '../../build-evidence/packaging-python.json'
    Assert-NoReparsePath $recordPath
    $record = Get-Content -LiteralPath $recordPath -Raw -Encoding utf8 | ConvertFrom-Json
    if (-not [IO.Path]::IsPathFullyQualified([string]$record.path)) { throw 'Recorded MSYS2 Python path is not absolute.' }
    Assert-FileMatchesRecord $record.path $record 'Same-run packaging Python' | Out-Null
    return [string]$record.path
}

function Get-WindowQualification([Diagnostics.Process]$Process, [string]$OutputDirectory, [string]$ExpectedTitle) {
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    $root = [Windows.Automation.AutomationElement]::FromHandle($Process.MainWindowHandle)
    if (-not $root) { throw 'UI Automation could not bind the activated main window.' }
    $rootBounds = $root.Current.BoundingRectangle
    if (-not (Test-DayQuayWindowTitle $root.Current.Name $ExpectedTitle) -or $root.Current.ProcessId -ne $Process.Id) { throw 'UIA root is not the exact owned DayQuay window.' }
    if ($root.Current.IsOffscreen -or $rootBounds.Width -lt 400 -or $rootBounds.Height -lt 300 -or $rootBounds.Width -gt 8192 -or $rootBounds.Height -gt 8192) { throw 'Activated main window is not visibly rendered.' }
    $topLevelWindows = [Collections.Generic.List[object]]::new()
    $processCondition = [Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ProcessIdProperty, $Process.Id)
    $desktopWindows = [Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children, $processCondition)
    if ($desktopWindows.Count -gt 32) { throw 'Owned top-level UI exceeds bounded capture.' }
    for ($index = 0; $index -lt $desktopWindows.Count; $index++) {
        $window = $desktopWindows.Item($index)
        $name = [string]$window.Current.Name
        if ($name.Length -gt 512) { throw 'Top-level UI name exceeds bounded capture.' }
        $modal = $null
        if (-not $window.Current.IsOffscreen -and ($name -match '(?i)\b(error|exception|warning|traceback)\b' -or
            $window.Current.ClassName -ceq '#32770' -or
            ($window.TryGetCurrentPattern([Windows.Automation.WindowPattern]::Pattern,[ref]$modal) -and $modal.Current.IsModal))) {
            throw "Error/modal top-level surface detected: $name"
        }
        $topLevelWindows.Add([ordered]@{ name=$name; offscreen=[bool]$window.Current.IsOffscreen })
    }
    $items = [Collections.Generic.List[object]]::new()
    $actionable = 0
    $descendants = $root.FindAll([Windows.Automation.TreeScope]::Subtree, [Windows.Automation.Condition]::TrueCondition)
    if ($descendants.Count -gt 1000) { throw 'UIA window tree exceeds bounded capture.' }
    $limit = $descendants.Count
    for ($index = 0; $index -lt $limit; $index++) {
        $element = $descendants.Item($index)
        try {
            $name = [string]$element.Current.Name
            if ($name.Length -gt 512) { throw 'Error surface detected: unbounded UI text.' }
            $control = [string]$element.Current.ControlType.ProgrammaticName
            $enabled = [bool]$element.Current.IsEnabled
            $offscreen = [bool]$element.Current.IsOffscreen
            if ($name -match '(?i)unhandled exception|traceback|fatal error|script error') {
                throw "Error surface detected in activated UI: $name"
            }
            if ($enabled -and -not $offscreen -and $name -and $control -match 'ControlType\.(Button|MenuItem|Edit|ComboBox|ListItem)') {
                $actionable++
            }
            $items.Add([ordered]@{ name=$name; control_type=$control; enabled=$enabled; offscreen=$offscreen; process_id=$element.Current.ProcessId })
        } catch {
            if ($_.Exception.Message -match '^Error surface detected') { throw }
        }
    }
    $treePath = Join-Path $OutputDirectory 'accessible-window-tree.json'
    Write-NewUtf8Json $treePath @($items)
    $screenshotCaptured = $false
    $screenshotError = $null
    $screenshotHash = $null
    $captureGeometry = @{}
    $colors = [Collections.Generic.HashSet[int]]::new()
    try {
        Add-Type -AssemblyName System.Drawing
        Add-Type -AssemblyName System.Windows.Forms
        [DayQuayQualification.NativePackageProbe]::ShowWindow($Process.MainWindowHandle,9) | Out-Null
        [DayQuayQualification.NativePackageProbe]::SetForegroundWindow($Process.MainWindowHandle) | Out-Null
        Start-Sleep -Milliseconds 250
        $windowHandle=$Process.MainWindowHandle
        $observePlacement={
            $Process.Refresh()
            if ($Process.HasExited -or $Process.MainWindowHandle -ne $windowHandle) { throw 'Owned process/window changed during capture placement.' }
            [uint32]$owner=0
            [DayQuayQualification.NativePackageProbe]::GetWindowThreadProcessId($windowHandle,[ref]$owner) | Out-Null
            if ($owner -ne $Process.Id -or $root.Current.ProcessId -ne $Process.Id) { throw 'Capture window no longer belongs to the retained process.' }
            $bounds=$root.Current.BoundingRectangle
            $area=[Windows.Forms.Screen]::FromHandle($windowHandle).WorkingArea
            $desktop=[Windows.Forms.SystemInformation]::VirtualScreen
            return @{process_id=[int]$owner;title=[string]$root.Current.Name;visible=(-not $root.Current.IsOffscreen);
                bounds=@{x=$bounds.X;y=$bounds.Y;width=$bounds.Width;height=$bounds.Height};
                work_area=@{x=$area.X;y=$area.Y;width=$area.Width;height=$area.Height};
                virtual_screen=@{x=$desktop.X;y=$desktop.Y;width=$desktop.Width;height=$desktop.Height}}
        }.GetNewClosure()
        $movePlacement={param($requested)
            # Recheck the same live process and HWND immediately before the only
            # native mutation. Never enumerate or reposition another process.
            $Process.Refresh()
            [uint32]$owner=0
            [DayQuayQualification.NativePackageProbe]::GetWindowThreadProcessId($windowHandle,[ref]$owner) | Out-Null
            if ($Process.HasExited -or $Process.MainWindowHandle -ne $windowHandle -or $owner -ne $Process.Id) { throw 'Refusing to move an unowned capture window.' }
            # ASYNCWINDOWPOS | NOACTIVATE | NOZORDER: the bounded observation
            # loop, not a synchronous cross-thread move, proves completion.
            if (-not [DayQuayQualification.NativePackageProbe]::SetWindowPos($windowHandle,[IntPtr]::Zero,
                $requested.x,$requested.y,$requested.width,$requested.height,0x4014)) {
                throw [ComponentModel.Win32Exception]::new([Runtime.InteropServices.Marshal]::GetLastWin32Error(),'Cannot fit the owned capture window.')
            }
        }.GetNewClosure()
        Set-DayQuayCapturePlacement $Process.Id $ExpectedTitle @{
            Observe=$observePlacement;Move=$movePlacement;Wait={Start-Sleep -Milliseconds 250}
        } $captureGeometry
        [uint32]$foregroundPid=0
        [DayQuayQualification.NativePackageProbe]::GetWindowThreadProcessId(
            [DayQuayQualification.NativePackageProbe]::GetForegroundWindow(),[ref]$foregroundPid) | Out-Null
        if ($foregroundPid -ne $Process.Id) { throw 'Owned window is not foreground for screenshot.' }
        $latest=& $observePlacement
        Assert-DayQuayCaptureBounds $latest.bounds $latest.work_area
        if ($latest.title -cne $ExpectedTitle -or -not $latest.visible) { throw 'Owned title/visibility changed before screenshot.' }
        $captureGeometry.after=$latest
        $rootBounds=$latest.bounds
        $bounds=$rootBounds
        if ($bounds.Width -lt 400 -or $bounds.Height -lt 300 -or $bounds.Width -gt 8192 -or $bounds.Height -gt 8192) { throw 'Window resized outside bounded screenshot dimensions.' }
        $rectangle=[Drawing.Rectangle]::new([int]$bounds.X,[int]$bounds.Y,[int]$bounds.Width,[int]$bounds.Height)
        if (-not [Windows.Forms.SystemInformation]::VirtualScreen.Contains($rectangle)) { throw 'Owned window is outside the visible desktop.' }
        $bitmap = [Drawing.Bitmap]::new([int][Math]::Ceiling($bounds.Width), [int][Math]::Ceiling($bounds.Height))
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.CopyFromScreen([int]$bounds.X, [int]$bounds.Y, 0, 0, $bitmap.Size)
            $bitmap.Save((Join-Path $OutputDirectory 'qualification-window.png'), [Drawing.Imaging.ImageFormat]::Png)
            for ($y=0;$y -lt $bitmap.Height;$y+=7) { for ($x=0;$x -lt $bitmap.Width;$x+=7) { $colors.Add($bitmap.GetPixel($x,$y).ToArgb()) | Out-Null } }
            $screenshotHash=(Get-FileHash (Join-Path $OutputDirectory 'qualification-window.png') -Algorithm SHA256).Hash.ToLowerInvariant()
            $screenshotCaptured = $true
        } finally {
            $graphics.Dispose()
            $bitmap.Dispose()
        }
    } catch {
        $screenshotError = $_.Exception.Message
    }
    $snapshot = [ordered]@{
        expected_title=$ExpectedTitle; title=$root.Current.Name; process_id=$Process.Id; visible=(-not $root.Current.IsOffscreen)
        width=$rootBounds.Width; height=$rootBounds.Height; controls=@($items)
        screenshot_sha256=$screenshotHash; sampled_colors=$colors.Count
        accessible_elements = $items.Count
        top_level_windows = @($topLevelWindows)
        actionable_controls_verified = ($actionable -gt 0)
        actionable_control_count = $actionable
        screenshot_captured = $screenshotCaptured
        screenshot_error = $screenshotError
        capture_geometry = $captureGeometry
        startup_limited = ($actionable -eq 0)
        accessibility_scope = 'GTK startup only; journal/backup/restore workflows untested'
    }
    Write-NewUtf8Json (Join-Path $OutputDirectory 'window-observation.json') $snapshot
    Assert-DayQuayWindowEvidence $snapshot $ExpectedTitle
    return $snapshot
}

function Assert-DayQuayFailureCaptureSnapshot($Snapshot, [int]$ProcessId, [int64]$WindowHandle, [string]$Title) {
    if ($Snapshot.process_id -ne $ProcessId -or $Snapshot.window_handle -ne $WindowHandle -or
        $Snapshot.title -cne $Title -or -not $Snapshot.visible -or
        $Snapshot.foreground_window_handle -ne $WindowHandle) { throw 'Failure capture is not the exact owned foreground dialog.' }
    Assert-DayQuayFiniteRectangle $Snapshot.bounds
    Assert-DayQuayFiniteRectangle $Snapshot.virtual_screen
    $bounds=$Snapshot.bounds; $desktop=$Snapshot.virtual_screen
    if ($bounds.width -gt 2048 -or $bounds.height -gt 2048 -or ($bounds.width*$bounds.height) -gt 2097152 -or
        $bounds.x -lt $desktop.x -or $bounds.y -lt $desktop.y -or
        ($bounds.x+$bounds.width) -gt ($desktop.x+$desktop.width) -or
        ($bounds.y+$bounds.height) -gt ($desktop.y+$desktop.height)) { throw 'Failure dialog is outside bounded visible desktop capture.' }
}

function Invoke-DayQuayFailureCapture([int]$ProcessId, [int64]$WindowHandle, [string]$Title, [Collections.IDictionary]$Operations, [Collections.IDictionary]$Evidence) {
    $Evidence.before=& $Operations.Observe
    Assert-DayQuayFailureCaptureSnapshot $Evidence.before $ProcessId $WindowHandle $Title
    [byte[]]$bytes=& $Operations.Capture $Evidence.before.bounds
    if (-not $bytes.Length -or $bytes.Length -gt 1000000) { throw 'Failure screenshot exceeds the bounded PNG evidence size.' }
    $Evidence.after=& $Operations.Observe
    Assert-DayQuayFailureCaptureSnapshot $Evidence.after $ProcessId $WindowHandle $Title
    foreach($field in @('x','y','width','height')) {
        if ($Evidence.before.bounds.$field -ne $Evidence.after.bounds.$field) { throw 'Failure dialog moved during screenshot capture.' }
    }
    return ,$bytes
}

function Write-DayQuayConsumerWindowFailure([Diagnostics.Process]$Process, [string]$FailurePath, [string]$OutputDirectory) {
    $evidence=[ordered]@{diagnostic_only=$true;workflow_qualified=$false;process_id=$Process.Id;
        screenshot_captured=$false;screenshot_sha256=$null;capture_error=$null;geometry=@{};controls=@()}
    try {
        $failure=Get-Content -LiteralPath $FailurePath -Raw -Encoding utf8 | ConvertFrom-Json
        if ($failure.process_id -ne $Process.Id -or $failure.workflow_qualified) { throw 'Failure receipt does not belong to the retained consumer process.' }
        $target=$failure.diagnostics.input_target
        $windowHandle=[IntPtr]::new([int64]$target.hwnd)
        $title=[string]$target.title
        if ($windowHandle -eq [IntPtr]::Zero -or -not $title -or $title.Length -gt 512) { throw 'Failure receipt has no bounded pinned input target.' }
        $evidence.input_target=@{hwnd=$windowHandle.ToInt64();title=$title}
        Add-Type -AssemblyName UIAutomationClient
        Add-Type -AssemblyName UIAutomationTypes
        Add-Type -AssemblyName System.Drawing
        Add-Type -AssemblyName System.Windows.Forms
        $observe={
            $Process.Refresh()
            if ($Process.HasExited) { throw 'Retained consumer process exited before failure capture.' }
            [uint32]$owner=0
            [DayQuayQualification.NativePackageProbe]::GetWindowThreadProcessId($windowHandle,[ref]$owner) | Out-Null
            if ($owner -ne $Process.Id) { throw 'Failure window no longer belongs to the retained process.' }
            $root=[Windows.Automation.AutomationElement]::FromHandle($windowHandle)
            if (-not $root -or $root.Current.ProcessId -ne $Process.Id) { throw 'Failure UIA root is not owned.' }
            $rectangle=$root.Current.BoundingRectangle
            $desktop=[Windows.Forms.SystemInformation]::VirtualScreen
            return @{process_id=[int]$owner;window_handle=$windowHandle.ToInt64();
                title=[string]$root.Current.Name;visible=(-not $root.Current.IsOffscreen);
                foreground_window_handle=[DayQuayQualification.NativePackageProbe]::GetForegroundWindow().ToInt64();
                bounds=@{x=[Math]::Floor($rectangle.X);y=[Math]::Floor($rectangle.Y);
                    width=[Math]::Ceiling($rectangle.Right)-[Math]::Floor($rectangle.X);
                    height=[Math]::Ceiling($rectangle.Bottom)-[Math]::Floor($rectangle.Y)};
                virtual_screen=@{x=$desktop.X;y=$desktop.Y;width=$desktop.Width;height=$desktop.Height}}
        }.GetNewClosure()
        $capture={param($bounds)
            $bitmap=[Drawing.Bitmap]::new([int]$bounds.width,[int]$bounds.height)
            $graphics=$null;$buffer=[IO.MemoryStream]::new()
            try {
                $graphics=[Drawing.Graphics]::FromImage($bitmap)
                $graphics.CopyFromScreen([int]$bounds.x,[int]$bounds.y,0,0,$bitmap.Size)
                $bitmap.Save($buffer,[Drawing.Imaging.ImageFormat]::Png)
                return ,$buffer.ToArray()
            } finally {
                if ($graphics) {$graphics.Dispose()};$bitmap.Dispose();$buffer.Dispose()
            }
        }
        [byte[]]$bytes=Invoke-DayQuayFailureCapture $Process.Id $windowHandle.ToInt64() $title @{Observe=$observe;Capture=$capture} $evidence.geometry
        $imagePath=Join-Path $OutputDirectory 'installed-consumer-window-failure.png'
        $stream=[IO.FileStream]::new($imagePath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try {$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)} finally {$stream.Dispose()}
        $evidence.screenshot_captured=$true
        $evidence.screenshot_sha256=(Get-FileHash -LiteralPath $imagePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $root=[Windows.Automation.AutomationElement]::FromHandle($windowHandle)
        $elements=$root.FindAll([Windows.Automation.TreeScope]::Subtree,[Windows.Automation.Condition]::TrueCondition)
        $controls=[Collections.Generic.List[object]]::new()
        for($index=0;$index -lt [Math]::Min(128,$elements.Count);$index++) {
            $element=$elements.Item($index)
            if ($element.Current.ProcessId -ne $Process.Id) { continue }
            $name=[string]$element.Current.Name
            $item=[ordered]@{name=$name.Substring(0,[Math]::Min(512,$name.Length));
                control_type=[string]$element.Current.ControlType.ProgrammaticName;
                keyboard_focus=[bool]$element.Current.HasKeyboardFocus;enabled=[bool]$element.Current.IsEnabled;
                value=$null;value_exposed=$false}
            $pattern=$null
            if (-not $element.Current.IsPassword -and $element.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern,[ref]$pattern)) {
                $value=[string]$pattern.Current.Value
                $item.value=$value.Substring(0,[Math]::Min(4096,$value.Length));$item.value_exposed=$true
            }
            $controls.Add($item)
        }
        $evidence.controls=@($controls)
        $evidence.control_tree_truncated=($elements.Count -gt 128)
        $evidence.focus_scope='Available owned UIA focus/values only; GTK may expose just its root. Inspect the owned screenshot for path text and default-button appearance.'
    } catch {$evidence.capture_error=$_.Exception.Message}
    Write-NewUtf8Json (Join-Path $OutputDirectory 'installed-consumer-window-failure.json') $evidence
}

function Write-NewUtf8Json([string]$Path, [object]$Value) {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Value | ConvertTo-Json -Depth 20) + [Environment]::NewLine)
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
}

function Write-NewUtf8Text([string]$Path, [string]$Value) {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($Value)
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
}

function New-DayQuayWorkflowProfile([string]$ProfileRoot, [string]$OwnershipToken) {
    if (-not $OwnershipToken -or $OwnershipToken -cnotmatch '^[0-9a-f]{32}$') { throw 'Invalid workflow-profile ownership token.' }
    if (Test-Path -LiteralPath $ProfileRoot) { throw 'Existing DayQuay profile must be preserved.' }
    Assert-NoReparsePath ([IO.Path]::GetDirectoryName((Get-CanonicalPath $ProfileRoot)))
    New-Item -ItemType Directory -Path $ProfileRoot -ErrorAction Stop | Out-Null
    $ownership = $null
    try {
        Assert-NoReparsePath $ProfileRoot
        $marker = Join-Path $ProfileRoot '.dayquay-qualification-owner'
        Write-NewUtf8Text $marker $OwnershipToken
        $ownership = [ordered]@{
            root = Get-CanonicalPath $ProfileRoot
            marker = Get-CanonicalPath $marker
            marker_sha256 = (Get-FileHash -LiteralPath $marker -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        New-Item -ItemType Directory -Path (Join-Path $ProfileRoot 'data') -ErrorAction Stop | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $ProfileRoot 'ReopenProbe') -ErrorAction Stop | Out-Null
        Write-NewUtf8Text (Join-Path $ProfileRoot 'configuration.cfg') "firstStart=0`n"
        return $ownership
    } catch {
        $preparationError = $_.Exception.Message
        if (-not $ownership) {
            throw "$preparationError Workflow profile preparation cleanup ownership is unproven; path preserved."
        }
        try {
            Remove-DayQuayWorkflowProfile $ownership | Out-Null
        } catch {
            throw "$preparationError Workflow profile preparation cleanup failed; path preserved: $($_.Exception.Message)"
        }
        throw
    }
}

function Remove-DayQuayWorkflowProfile($Ownership) {
    if (-not $Ownership) { return $false }
    $root = Get-CanonicalPath ([string]$Ownership.root)
    $marker = Get-CanonicalPath ([string]$Ownership.marker)
    if (-not (Test-PathInside $marker $root) -or -not (Test-Path -LiteralPath $root -PathType Container)) {
        throw 'Owned workflow profile identity is missing or outside its root.'
    }
    Assert-NoReparsePath $root
    Assert-NoReparsePath $marker
    if ((Get-FileHash -LiteralPath $marker -Algorithm SHA256).Hash.ToLowerInvariant() -cne [string]$Ownership.marker_sha256) {
        throw 'Owned workflow profile marker changed; profile preserved.'
    }
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction Stop
    if (Test-Path -LiteralPath $root) { throw 'Owned workflow profile remains after cleanup.' }
    return $true
}

function Invoke-DayQuayInstallQualification([string]$PackagePath, [string]$RecordPath, [string]$SignToolPath, [string]$OutputPath) {
    $state = [ordered]@{
        package = $null; record = $null; output = $null; temporary = $null; signedCopy = $null
        publicCertificate = $null; certificate = $null; trustedCertificate = $null; trustAttempted = $false
        installed = $null; installedByUs = $false; process = $null; processOwned = $false; cleanupProcessExit = $null
        installAttempted = $false; brokerProcessId = 0; addCompleted = $false; ownedPackageFullName = $null; preflightPackageFullNames = @(); residualPackageFullNames = @(); processHandle = $null; processExit = $null
        unsignedPackageSha256 = $null; signedPackageSha256 = $null; signTool = $null
        aumid = $null; processPackageFullName = $null; modules = @(); window = $null
        executableSha256 = $null; expectedTitle = $null
        cleanClose = $false; uninstallVerified = $false; processShutdownVerified = $false
        workflowProfile = $null; workflowProfileRemoved = $false; workflowEvidence = $null; workflowTested = $false
        workflowArchive = $null; workflowRestoreName = 'RestoredQualification'; workflowSentinel = $null; workflowReopenMarker = $null
        workflowDiagnosticError = $null
    }
    $expectedIdentity = [ordered]@{
        packageName='Trieflow.DayQuay.Qualification'; publisher='CN=DayQuay-CI-Qualification'; version='1.0.0.0'
        architecture='x64'; applicationId='DayQuay'; executable='DayQuay.exe'
        deviceFamily='Windows.Desktop'; minVersion='10.0.19041.0'; maxVersionTested='10.0.26100.0'; capability='runFullTrust'
    }

    $operations = [ordered]@{}
    $operations.Preflight = {
        if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or $env:CI -ne 'true') { throw 'Requires an isolated disposable Windows CI runner.' }
        foreach ($argument in @($PackagePath,$RecordPath,$SignToolPath,$OutputPath)) {
            if (-not $argument) { throw 'Package, package record, SignTool, and output are required.' }
        }
        $state.package = (Resolve-Path -LiteralPath $PackagePath).Path
        $recordFile = (Resolve-Path -LiteralPath $RecordPath).Path
        $state.signTool = (Resolve-Path -LiteralPath $SignToolPath).Path
        if ([IO.Path]::GetFileName($state.signTool) -ine 'signtool.exe') { throw 'Exact SignTool.exe path is required.' }
        $outputCandidate = [IO.Path]::GetFullPath($OutputPath)
        if (Test-Path -LiteralPath $outputCandidate) { throw 'Qualification output already exists and will not be replaced.' }
        New-Item -ItemType Directory -Path $outputCandidate -ErrorAction Stop | Out-Null
        $state.output = $outputCandidate
        $state.record = Get-Content -LiteralPath $recordFile -Raw -Encoding utf8 | ConvertFrom-Json
        if ($state.record.sourceCommit -cne $env:GITHUB_SHA) { throw 'Package source differs from this qualification run.' }
        Invoke-CheckedNative (Get-DayQuayPackagingPython) @(
            (Join-Path $PSScriptRoot 'verify_record.py'),'--record',$recordFile,'--package',$state.package,'--source-commit',$env:GITHUB_SHA)
        $state.expectedTitle = [string]$state.record.windowTitleContract.expectedTitle
        if ($state.record.schemaVersion -ne 1 -or -not $state.record.qualificationIdentityOnly -or $state.record.signed -or $state.record.publicRelease -or $state.record.licenseClearanceClaimed -or $state.record.installationQualificationPassed) {
            throw 'Package record is not an unsigned qualification-only record.'
        }
        foreach ($field in $expectedIdentity.Keys) {
            if ([string]$state.record.identity.$field -cne [string]$expectedIdentity[$field]) { throw "Qualification identity mismatch: $field" }
        }
        $state.unsignedPackageSha256 = (Get-FileHash -LiteralPath $state.package -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($state.unsignedPackageSha256 -ne ([string]$state.record.containerVerification.package.sha256).ToLowerInvariant()) { throw 'Unsigned package hash differs from verified package record.' }
        $sdkVersion = [regex]::Escape([string]$state.record.makeAppx.sdkVersion)
        if ([string]$state.record.makeAppx.sdkVersion -cne '10.0.26100.0') { throw 'Only Windows SDK 10.0.26100.0 is qualified.' }
        Assert-FileMatchesRecord $state.record.makeAppx.path $state.record.makeAppx 'MakeAppx tool' | Out-Null
        if ($state.signTool -notmatch "(?i)[\\/]$sdkVersion[\\/]x64[\\/]signtool\.exe$") { throw 'SignTool does not match the exact qualified Windows SDK x64 directory.' }
        if ([IO.Path]::GetDirectoryName($state.signTool) -ine [IO.Path]::GetDirectoryName([string]$state.record.makeAppx.path)) { throw 'SignTool is not the exact sibling of the qualified MakeAppx tool.' }
        $state.signTool = [ordered]@{
            path = $state.signTool
            bytes = (Get-Item -LiteralPath $state.signTool).Length
            sha256 = (Get-FileHash -LiteralPath $state.signTool -Algorithm SHA256).Hash.ToLowerInvariant()
            sdk_version = [string]$state.record.makeAppx.sdkVersion
        }
        foreach ($profile in @((Join-Path $env:APPDATA 'DayQuay'), (Join-Path $env:USERPROFILE '.rednotebook'))) {
            if (Test-Path -LiteralPath $profile) { throw 'Existing DayQuay/legacy user profile must be preserved; disposable-run qualification refused.' }
        }
        $existing = @(Get-AppxPackage -Name $expectedIdentity.packageName -ErrorAction Stop)
        $state.preflightPackageFullNames = @($existing | ForEach-Object { [string]$_.PackageFullName })
        if ($existing.Count -gt 0) { throw 'A matching DayQuay qualification package is already installed; refusing to replace or remove it.' }
    }.GetNewClosure()

    $operations.PrepareSignedCopy = {
        $runnerTemp = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
        $temporaryCandidate = Join-Path $runnerTemp ('.dayquay-install-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $temporaryCandidate -ErrorAction Stop | Out-Null
        # Cleanup ownership starts only after exclusive creation succeeds.
        $state.temporary = $temporaryCandidate
        $state.signedCopy = Join-Path $state.temporary 'DayQuay.Qualification.signed.msix'
        [IO.File]::Copy($state.package, $state.signedCopy, $false)
        $state.publicCertificate = Join-Path $state.temporary 'DayQuay.Qualification.public.cer'
        $state.certificate = New-SelfSignedCertificate -Type Custom -KeyUsage DigitalSignature -KeyExportPolicy NonExportable -KeySpec Signature `
            -CertStoreLocation 'Cert:\CurrentUser\My' -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3','2.5.29.19={text}') `
            -Subject $expectedIdentity.publisher -FriendlyName 'DayQuay ephemeral CI qualification' -NotAfter (Get-Date).AddHours(12)
        Export-Certificate -Cert $state.certificate -FilePath $state.publicCertificate -Force | Out-Null
        $state.trustAttempted = $true
        $state.trustedCertificate = Import-Certificate -FilePath $state.publicCertificate -CertStoreLocation 'Cert:\LocalMachine\TrustedPeople'
        foreach ($arguments in @(
            @('sign','/fd','SHA256','/sha1',$state.certificate.Thumbprint,'/s','My',$state.signedCopy),
            @('verify','/pa','/all','/v',$state.signedCopy)
        )) {
            if ((Get-Item -LiteralPath $state.signTool.path).Length -ne $state.signTool.bytes -or
                (Get-FileHash -LiteralPath $state.signTool.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $state.signTool.sha256) {
                throw 'SignTool changed after qualification preflight.'
            }
            Invoke-CheckedNative $state.signTool.path $arguments
        }
        if ((Get-Item -LiteralPath $state.signTool.path).Length -ne $state.signTool.bytes -or
            (Get-FileHash -LiteralPath $state.signTool.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $state.signTool.sha256) {
            throw 'SignTool changed during qualification signing.'
        }
        $signature = Get-AuthenticodeSignature -LiteralPath $state.signedCopy
        if ($signature.Status -ne [Management.Automation.SignatureStatus]::Valid -or $signature.SignerCertificate.Thumbprint -ne $state.certificate.Thumbprint) {
            throw "Test-copy signature is not valid for the ephemeral certificate: $($signature.Status)"
        }
        if ((Get-FileHash -LiteralPath $state.package -Algorithm SHA256).Hash.ToLowerInvariant() -ne $state.unsignedPackageSha256) { throw 'Unsigned source package changed during signing.' }
        $state.signedPackageSha256 = (Get-FileHash -LiteralPath $state.signedCopy -Algorithm SHA256).Hash.ToLowerInvariant()
    }.GetNewClosure()

    $operations.PrepareWorkflowFixture = {
        $state.workflowProfile = New-DayQuayWorkflowProfile `
            -ProfileRoot (Join-Path $env:APPDATA 'DayQuay') `
            -OwnershipToken ([guid]::NewGuid().ToString('N'))
        $state.workflowArchive = Join-Path $state.temporary 'DayQuay-consumer-backup.zip'
        $state.workflowSentinel = 'DAYQUAY-INSTALLED-WORKFLOW-' + [guid]::NewGuid().ToString('N').ToUpperInvariant()
        $state.workflowReopenMarker = 'DAYQUAY-REOPENED-WORKFLOW-' + [guid]::NewGuid().ToString('N').ToUpperInvariant()
    }.GetNewClosure()

    $operations.Install = {
        $state.installAttempted = $true
        Add-AppxPackage -Path $state.signedCopy -ErrorAction Stop
        $state.addCompleted = $true
        $matches = @(Get-AppxPackage -Name $expectedIdentity.packageName -ErrorAction Stop)
        if ($matches.Count -ne 1) { throw 'Expected exactly one installed qualification package.' }
        $candidate = $matches[0]
        if ([string]$candidate.Name -cne $expectedIdentity.packageName -or
            [string]$candidate.Publisher -cne $expectedIdentity.publisher -or
            [string]$candidate.Version -cne $expectedIdentity.version -or
            [string]$candidate.Architecture -cne 'X64' -or
            -not ([string]$candidate.PackageFullName).StartsWith($expectedIdentity.packageName + '_' + $expectedIdentity.version + '_x64_', [StringComparison]::Ordinal) -or
            -not [string]$candidate.PackageFamilyName) {
            throw 'Installed publisher/version/architecture differs from qualification identity.'
        }
        # Ownership is established only after our Add succeeds and one exact
        # expected registration is observed. A failed/partial Add cannot confer it.
        $state.installed = $candidate
        $state.ownedPackageFullName = [string]$candidate.PackageFullName
        $state.installedByUs = $true
        $state.aumid = [string]$state.installed.PackageFamilyName + '!' + $expectedIdentity.applicationId
        foreach ($entry in $state.record.payload.PSObject.Properties) {
            $relative = $entry.Name
            $expected = Get-RecordPayloadEntry $state.record $relative
            $hash = Assert-FileMatchesRecord (Join-Path $state.installed.InstallLocation ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)) $expected $relative
            if ($relative -eq 'DayQuay.exe') { $state.executableSha256 = $hash }

        }
    }.GetNewClosure()

    $operations.ActivateAndVerify = {
        Invoke-CheckedNative (Get-DayQuayPackagingPython) @(
            (Join-Path $PSScriptRoot 'verify_record.py'),'--record',$RecordPath,'--package',$state.package,
            '--source-commit',$env:GITHUB_SHA,'--installed-root',$state.installed.InstallLocation)
        Add-DayQuayActivationTypes
        $processId = [DayQuayQualification.ActivationBroker]::Activate($state.aumid)
        $state.brokerProcessId = [int]$processId
        $state.process = [Diagnostics.Process]::GetProcessById([int]$processId)
        $state.processHandle = $state.process.SafeHandle
        if ($state.processHandle.IsInvalid -or $state.processHandle.IsClosed) { throw 'Cannot retain the live broker-activated process handle.' }
        $expectedExecutable = Get-CanonicalPath (Join-Path $state.installed.InstallLocation 'DayQuay.exe')
        if ((Get-CanonicalPath $state.process.MainModule.FileName) -ine $expectedExecutable) { throw 'Broker returned an executable outside the owned installed path.' }
        $state.processPackageFullName = [DayQuayQualification.NativePackageProbe]::GetFullName($state.process.Handle)
        if ($state.processPackageFullName -cne $state.ownedPackageFullName) { throw 'Broker process does not have the exact owned package identity.' }
        Assert-FileMatchesRecord $expectedExecutable (Get-RecordPayloadEntry $state.record 'DayQuay.exe') 'Activated executable' | Out-Null
        $state.processOwned = $true
        $deadline = [DateTime]::UtcNow.AddSeconds(30)
        do {
            Start-Sleep -Milliseconds 250
            $state.process.Refresh()
            if ($state.process.HasExited) { throw "Activated DayQuay exited during startup: $($state.process.ExitCode)" }
        } until (($state.process.MainWindowHandle -ne 0 -and (Test-DayQuayWindowTitle $state.process.MainWindowTitle $state.expectedTitle)) -or [DateTime]::UtcNow -ge $deadline)
        if ($state.process.MainWindowHandle -eq 0) { throw 'Activated DayQuay did not create a main window.' }
        if (-not (Test-DayQuayWindowTitle $state.process.MainWindowTitle $state.expectedTitle)) { throw "Unexpected activated main-window title: $($state.process.MainWindowTitle)" }
        $state.processPackageFullName = [DayQuayQualification.NativePackageProbe]::GetFullName($state.process.Handle)
        if ($state.processPackageFullName -cne [string]$state.installed.PackageFullName) { throw 'Activated process does not own the exact installed package full name.' }
        Start-Sleep -Seconds 3
        $state.process.Refresh()
        if ($state.process.HasExited -or $state.process.MainWindowHandle -eq 0 -or -not (Test-DayQuayWindowTitle $state.process.MainWindowTitle $state.expectedTitle)) { throw 'Activated DayQuay did not survive the stable-window interval.' }
        $installRoot = Get-CanonicalPath $state.installed.InstallLocation
        $windowsRoot = Get-CanonicalPath $env:SystemRoot
        $modules = [Collections.Generic.List[object]]::new()
        $requiredRuntime = @{}
        foreach ($entry in $state.record.runtime.PSObject.Properties) { $requiredRuntime[[string]$entry.Value] = $false }
        foreach ($module in @($state.process.Modules)) {
            Assert-NoReparsePath $module.FileName
            $path = Get-CanonicalPath $module.FileName
            $platformSignature = $null
            if (Test-PathInside $path $installRoot) {
                $relative = $path.Substring($installRoot.Length).TrimStart('\','/').Replace('\','/')
                $expected = Get-RecordPayloadEntry $state.record $relative
                $hash = Assert-FileMatchesRecord $path $expected "Loaded module $relative"
                if ($requiredRuntime.ContainsKey($relative)) { $requiredRuntime[$relative] = $true }
                $origin = 'package'
            } elseif (Test-PathInside $path $windowsRoot) {
                $relative = $null
                $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
                $origin = 'windows'
            } else {
                $defenderRoot = Join-Path ([Environment]::GetFolderPath('CommonApplicationData')) 'Microsoft/Windows Defender/Platform'
                $platformSignature = Get-VerifiedDefenderModuleEvidence -Path $path -PlatformRoot $defenderRoot
                $relative = $null
                $hash = $platformSignature.sha256
                $origin = 'microsoft_defender_signed_platform'
            }
            $modules.Add([ordered]@{ name=$module.ModuleName; path=$path; origin=$origin; relative_path=$relative; sha256=$hash; platform_signature=$platformSignature })
        }
        foreach ($relative in $requiredRuntime.Keys) { if (-not $requiredRuntime[$relative]) { throw "Activated process did not load required packaged Python/GTK/Enchant runtime: $relative" } }
        $state.modules = @($modules)
        Write-NewUtf8Json (Join-Path $state.output 'loaded-modules.json') $state.modules
        $state.window = Get-WindowQualification $state.process $state.output $state.expectedTitle
        $workflowEvidencePath = Join-Path $state.output 'installed-consumer-workflow.json'
        try { Invoke-CheckedNative (Get-DayQuayPackagingPython) @(
            (Join-Path $PSScriptRoot 'installed_workflow_qualification.py'),
            '--process-id',[string]$state.process.Id,
            '--main-window-handle',[string]$state.process.MainWindowHandle.ToInt64(),
            '--initial-title',$state.expectedTitle,
            '--profile-root',[string]$state.workflowProfile.root,
            '--archive',$state.workflowArchive,
            '--restore-name',$state.workflowRestoreName,
            '--sentinel',$state.workflowSentinel,
            '--reopen-marker',$state.workflowReopenMarker,
            '--output',$workflowEvidencePath)
        } catch {
            $workflowError=$_
            try {
                Write-DayQuayConsumerWindowFailure $state.process `
                    (Join-Path $state.output 'installed-consumer-workflow-failure.json') $state.output
            } catch {$state.workflowDiagnosticError=$_.Exception.Message}
            throw $workflowError
        }
        $state.workflowEvidence = Get-Content -LiteralPath $workflowEvidencePath -Raw -Encoding utf8 | ConvertFrom-Json
        if ($state.workflowEvidence.schema_version -ne 1 -or
            -not $state.workflowEvidence.journal_backup_restore_workflow_tested -or
            $state.workflowEvidence.input_method -cne 'owned Win32 SendInput keyboard/mouse' -or
            $state.workflowEvidence.process_id -ne $state.process.Id -or
            $state.workflowEvidence.main_window_handle -ne $state.process.MainWindowHandle.ToInt64()) {
            throw 'Installed consumer workflow evidence is incomplete or belongs to another process/window.'
        }
        $state.workflowTested = $true
        $state.process.Refresh()
        if ($state.process.HasExited -or $state.process.MainWindowHandle -eq 0) { throw 'Activated DayQuay did not survive the stable-window interval.' }
    }.GetNewClosure()

    $operations.CloseCleanly = {
        if (-not $state.process.CloseMainWindow()) { throw 'Activated DayQuay refused a normal main-window close request.' }
        $state.processExit = Get-DayQuayProcessExitEvidence $state.process 15000
        if (-not $state.processExit.normal_exit) { throw ('Activated DayQuay normal-close observation failed: ' + ($state.processExit | ConvertTo-Json -Compress)) }
        $state.cleanClose = $true
        $state.processShutdownVerified = $true
    }.GetNewClosure()

    $operations.UninstallAndVerify = {
        if (-not $state.installedByUs -or -not $state.ownedPackageFullName) { throw 'Exact installed package ownership was not established.' }
        Remove-AppxPackage -Package $state.ownedPackageFullName -ErrorAction Stop
        if (@(Get-AppxPackage -Name $expectedIdentity.packageName -ErrorAction Stop).Count -ne 0) { throw 'Package registration remains after uninstall.' }
        $state.uninstallVerified = $true
    }.GetNewClosure()

    $operations.StopOwnedProcess = {
        # Retain and use the original attached Process/OS handle, never reacquire
        # a potentially recycled PID during cleanup.
        try {
            if ($state.processOwned -and $state.process -and $state.processHandle) {
                if (-not $state.process.HasExited) { $state.process.Kill() }
                $state.cleanupProcessExit = Get-DayQuayProcessExitEvidence $state.process 10000
                if (-not $state.cleanupProcessExit.wait_completed -or $state.cleanupProcessExit.observation_error) { throw ('Owned process cleanup failed: ' + ($state.cleanupProcessExit | ConvertTo-Json -Compress)) }
                $state.processShutdownVerified = $true
            }
        } finally {
            if ($state.process) { $state.process.Dispose() }
        }
    }.GetNewClosure()

    $operations.RemoveOwnedPackage = {
        if ($state.installAttempted) {
            $remaining = @(Get-AppxPackage -Name $expectedIdentity.packageName -ErrorAction Stop)
            $state.residualPackageFullNames = @($remaining | ForEach-Object { [string]$_.PackageFullName })
            if ($state.installedByUs -and $state.ownedPackageFullName) {
                $owned = @($remaining | Where-Object { [string]$_.PackageFullName -ceq $state.ownedPackageFullName })
                if ($owned.Count -gt 1) { throw 'Ambiguous duplicate registration state; all registrations preserved.' }
                if ($owned.Count -eq 1) { Remove-AppxPackage -Package $state.ownedPackageFullName -ErrorAction Stop }
            }
            # A matching registration after a failed Add may belong to another
            # invocation. Report residue without removing identity-tuple matches.
            $remaining = @(Get-AppxPackage -Name $expectedIdentity.packageName -ErrorAction Stop)
            $state.residualPackageFullNames = @($remaining | ForEach-Object { [string]$_.PackageFullName })
            if ($remaining.Count) { throw ('Unowned or unresolved package registrations preserved: ' + ($state.residualPackageFullNames -join ', ')) }
            if ($state.addCompleted -and -not $state.installedByUs) {
                throw 'Package cleanup uncertain: Add completed but exact registration ownership was never observed; empty queries do not prove absence. Any registration is preserved.'
            }
        }
    }.GetNewClosure()

    $operations.RemoveTrustedCertificate = {
        if ($state.trustAttempted -and $state.certificate) {
            $path = 'Cert:\LocalMachine\TrustedPeople\' + $state.certificate.Thumbprint
            if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force -ErrorAction Stop }
            if (Test-Path -LiteralPath $path) { throw 'Trusted public certificate remains after cleanup.' }
        }
    }.GetNewClosure()

    $operations.RemovePersonalCertificate = {
        if ($state.certificate) {
            $path = 'Cert:\CurrentUser\My\' + $state.certificate.Thumbprint
            if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -DeleteKey -Force -ErrorAction Stop }
            if (Test-Path -LiteralPath $path) { throw 'Ephemeral personal certificate remains after cleanup.' }
        }
    }.GetNewClosure()

    $operations.RemoveWorkflowFixture = {
        if ($state.workflowProfile) {
            if ($state.brokerProcessId -ne 0 -and -not $state.processShutdownVerified) {
                throw 'Activated process shutdown is unproven; workflow profile preserved.'
            }
            $state.workflowProfileRemoved = Remove-DayQuayWorkflowProfile $state.workflowProfile
        }
    }.GetNewClosure()

    $operations.RemoveTemporaryFiles = {
        if ($state.temporary -and (Test-Path -LiteralPath $state.temporary)) {
            Remove-Item -LiteralPath $state.temporary -Recurse -Force -ErrorAction Stop
            if (Test-Path -LiteralPath $state.temporary) { throw 'Temporary signed-copy directory remains after cleanup.' }
        }
    }.GetNewClosure()

    $result = Invoke-DayQuayQualificationCore -Operations $operations
    if (-not $state.output) {
        # An output collision is intentionally not overwritten and cannot receive evidence.
        throw $result.primary_error
    }
    $evidenceErrors = [Collections.Generic.List[string]]::new()
    $unsignedUnchanged = $false
    if ($state.unsignedPackageSha256 -and $state.package) {
        try {
            $unsignedUnchanged = (Get-FileHash -LiteralPath $state.package -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant() -eq $state.unsignedPackageSha256
            if (-not $unsignedUnchanged) { $evidenceErrors.Add('Unsigned package changed after qualification.') }
        } catch {
            $evidenceErrors.Add('Unsigned package final verification failed: ' + $_.Exception.Message)
        }
    } elseif ($result.installation_qualification_passed) {
        $evidenceErrors.Add('Successful core qualification did not retain the unsigned package identity.')
    }
    if ($result.installation_qualification_passed -and
        (-not $state.workflowTested -or -not $state.workflowEvidence -or -not $state.workflowProfileRemoved)) {
        $evidenceErrors.Add('Successful core qualification lacks installed workflow or owned profile-cleanup evidence.')
    }
    if ($result.installation_qualification_passed -and -not $state.processShutdownVerified) {
        $evidenceErrors.Add('Successful core qualification lacks verified activated-process shutdown.')
    }
    $qualificationPassed = $result.installation_qualification_passed -and $unsignedUnchanged -and $evidenceErrors.Count -eq 0
    $evidence = [ordered]@{
        schema_version = 1
        generated_at_utc = [DateTime]::UtcNow.ToString('o')
        source_commit = if ($state.record) { [string]$state.record.sourceCommit } else { $null }
        qualification_identity_only = $true
        identity = $expectedIdentity
        aumid = $state.aumid
        package_full_name = if ($state.installed) { [string]$state.installed.PackageFullName } else { $null }
        add_appx_completed = $state.addCompleted
        registration_ownership_established = $state.installedByUs
        owned_package_full_name = $state.ownedPackageFullName
        preflight_package_full_names = @($state.preflightPackageFullNames)
        residual_package_full_names = @($state.residualPackageFullNames)
        activated_process_package_full_name = $state.processPackageFullName
        unsigned_package_sha256 = $state.unsignedPackageSha256
        signed_copy_sha256 = $state.signedPackageSha256
        unsigned_package_unchanged = $unsignedUnchanged
        signtool = $state.signTool
        certificate_private_key_exported = $false
        executable_sha256 = $state.executableSha256
        loaded_module_count = @($state.modules).Count
        window = $state.window
        installed_consumer_workflow = $state.workflowEvidence
        workflow_diagnostic_error = $state.workflowDiagnosticError
        workflow_profile_removed = $state.workflowProfileRemoved
        process_exit = $state.processExit
        cleanup_process_exit = $state.cleanupProcessExit
        process_shutdown_verified = $state.processShutdownVerified
        process_identity_ownership_established = $state.processOwned
        clean_close_verified = $state.cleanClose
        uninstall_verified = $state.uninstallVerified
        installation_qualification_passed = $qualificationPassed
        workflow_acceptance = $false
        journal_backup_restore_workflow_tested = $state.workflowTested
        native_source_clearance = $false
        upgrade_tested = $false
        wack_tested = $false
        store_identity_used = $false
        public_release = $false
        primary_error = $result.primary_error
        cleanup_errors = @($result.cleanup_errors)
        evidence_errors = @($evidenceErrors)
    }
    try {
        Write-NewUtf8Json (Join-Path $state.output 'installation-qualification.json') $evidence
    } catch {
        throw "Could not preserve qualification JSON: $($_.Exception.Message). Primary: $($result.primary_error); cleanup: $($result.cleanup_errors -join '; '); evidence: $($evidenceErrors -join '; ')"
    }
    if (-not $qualificationPassed) {
        throw "DayQuay installation qualification failed. Primary: $($result.primary_error); cleanup: $($result.cleanup_errors -join '; '); evidence: $($evidenceErrors -join '; ')"
    }
    Write-Output 'PASS: broker-activated exact package, exercised installed journal/backup/restore, verified owned modules/window/close, uninstalled, and cleaned owned profile/certificate state.'
}

if (-not $LibraryOnly) {
    try {
        Invoke-DayQuayInstallQualification -PackagePath $Package -RecordPath $PackageRecord -SignToolPath $SignTool -OutputPath $Output
    } catch {
        Write-Error $_
        exit 1
    }
}
