#Requires -Version 7.2
[CmdletBinding()]
param(
    [ValidateSet('Prerequisites', 'Import', 'Configure', 'Export')]
    [string]$Stage = 'Prerequisites',
    [string]$Distro = 'Debian-Workstation',
    [string]$InstallLocation = "$env:LOCALAPPDATA\WSL\Debian-Workstation",
    [string]$Image,
    [string]$ImageSha256,
    [string]$ExportPath,
    [string]$LinuxUser = 'developer',
    [string]$BackgroundImage,
    [string]$PowerlineFont,
    [string]$FontFace = 'Cascadia Mono',
    [switch]$AllowExistingDistro
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot 'Workstation.psm1') -Force

function Invoke-Native([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe failed ($LASTEXITCODE)" }
}
function Write-Json([string]$Path, $Value) {
    $Value | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $Path -Encoding utf8NoBOM
}
function Backup-File([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        Copy-Item -LiteralPath $Path -Destination "$Path.wsl2-$(Get-Date -Format yyyyMMddHHmmss).bak"
    }
}
function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run this stage in an elevated PowerShell window.'
    }
}

if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'This release requires Windows x64.' }
if ($LinuxUser -notmatch '^[a-z_][a-z0-9_-]*$') { throw 'Invalid Linux username' }
if ($Distro -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]*$') { throw 'Invalid distro name' }
switch ($Stage) {
    'Prerequisites' {
        Assert-Admin
        Invoke-Native 'wsl.exe' @('--install', '--no-distribution')
        Write-Host 'If Windows requests a reboot, reboot and rerun this stage.'
        Invoke-Native 'wsl.exe' @('--update')
        Invoke-Native 'wsl.exe' @('--set-default-version', '2')
        foreach ($id in @('Microsoft.WindowsTerminal', 'Microsoft.VisualStudioCode', 'Git.Git')) {
            & winget.exe list --id $id --exact --accept-source-agreements | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Invoke-Native 'winget.exe' @('install', '--id', $id, '--exact', '--accept-package-agreements', '--accept-source-agreements')
            }
        }
    }
    'Import' {
        if (-not $Image -or -not $ImageSha256) { throw 'Supply a verified Debian 13 rootfs --Image and --ImageSha256.' }
        if ((Get-FileHash -LiteralPath $Image -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ImageSha256.ToLowerInvariant()) {
            throw 'Rootfs SHA256 mismatch'
        }
        $names = @(& wsl.exe --list --quiet) | ForEach-Object { ($_ -replace "`0", '').Trim() }
        if ($LASTEXITCODE -ne 0) { throw 'Cannot list WSL distributions' }
        if ($Distro -in $names) {
            if (-not $AllowExistingDistro) { throw "Distro $Distro exists. Refusing to alter it; choose another name." }
            Write-Host 'Existing distro preserved; no import performed.'
            return
        }
        Invoke-Native 'wsl.exe' @('--import', $Distro, $InstallLocation, $Image, '--version', '2')
        Write-Host "Imported $Distro. Run bootstrap-debian.sh inside it as root; no user is created by import."
    }
    'Configure' {
        if ([Environment]::OSVersion.Version.Build -lt 22621) { throw 'Mirrored networking requires a compatible Windows 11 installation.' }
        # Merge managed INI keys; preserve other sections, memory limits and comments.
        $path = Join-Path $env:USERPROFILE '.wslconfig'
        Backup-File $path
        $lines = if (Test-Path $path) { @(Get-Content -LiteralPath $path) } else { @() }
        $settings = @{ wsl2 = @{ networkingMode = 'mirrored'; dnsTunneling = 'false'; autoProxy = 'true' }; experimental = @{ hostAddressLoopback = 'true' } }
        @(Merge-IniSettings $lines $settings) | Set-Content -LiteralPath $path -Encoding utf8NoBOM

        $terminal = Join-Path $env:LOCALAPPDATA 'Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json'
        if (-not (Test-Path $terminal)) { throw 'Open Windows Terminal once, then rerun Configure.' }
        # PowerShell 7 supports Terminal JSON with comments. Merge only this profile.
        $config = Get-Content -LiteralPath $terminal -Raw | ConvertFrom-Json -AsHashtable
        $guid = '{f97bb340-b064-4c5a-9078-ab10ef8be192}'
        $terminalProfile = @{
            guid = $guid; name = $Distro; commandline = "wsl.exe -d `"$Distro`" -u $LinuxUser";
            startingDirectory = "\\wsl.localhost\$Distro\home\$LinuxUser\devops";
            colorScheme = 'Tango Dark'; cursorColor = '#8AE234'; cursorShape = 'filledBox';
            font = @{ face = $FontFace; size = 14 }; opacity = 100; useAcrylic = $false
        }
        $preferences = Join-Path $env:USERPROFILE '.wsl2-source-preferences'
        $sourceTerminal = Join-Path $preferences 'terminal.json'
        $sourceMetadata = Join-Path $preferences 'metadata.json'
        if (Test-Path -LiteralPath $sourceTerminal) {
            $sourceConfig = Get-Content $sourceTerminal -Raw | ConvertFrom-Json -AsHashtable
            $oldHome = ''
            if (Test-Path $sourceMetadata) {
                $metadata = Get-Content $sourceMetadata -Raw | ConvertFrom-Json -AsHashtable
                $oldHome = $metadata.old_windows_home
            }
            Merge-TerminalPreferences $config $sourceConfig $terminalProfile $oldHome $env:USERPROFILE
        }
        if ($PSBoundParameters.ContainsKey('FontFace')) { $terminalProfile.font.face = $FontFace }
        if ($BackgroundImage) {
            if (-not (Test-Path -LiteralPath $BackgroundImage)) { throw 'Background image missing' }
            $terminalProfile.backgroundImage = (Resolve-Path -LiteralPath $BackgroundImage).Path
            $terminalProfile.backgroundImageOpacity = 0.22
        }
        if (-not $config.ContainsKey('profiles')) { $config.profiles = @{ list = @() } }
        if (-not $config.profiles.ContainsKey('list')) { $config.profiles.list = @() }
        $existing = @($config.profiles.list | Where-Object { $_.guid -eq $guid })
        if ($existing.Count) {
            foreach ($key in $terminalProfile.Keys) { $existing[0][$key] = $terminalProfile[$key] }
        } else { $config.profiles.list = @($config.profiles.list) + @($terminalProfile) }
        $config.defaultProfile = $guid
        Backup-File $terminal
        Write-Json $terminal $config
        $codeSettings = Join-Path $env:APPDATA 'Code\User\settings.json'
        $sourceCode = Join-Path $preferences 'code-settings.json'
        if (Test-Path -LiteralPath $sourceCode) {
            $targetSettings = if (Test-Path $codeSettings) { Get-Content $codeSettings -Raw | ConvertFrom-Json -AsHashtable } else { @{} }
            $sourceSettings = Get-Content $sourceCode -Raw | ConvertFrom-Json -AsHashtable
            Merge-JsonMap $targetSettings $sourceSettings
            New-Item -ItemType Directory -Path (Split-Path $codeSettings) -Force | Out-Null
            Backup-File $codeSettings
            Write-Json $codeSettings $targetSettings
        }
        $sourceKeys = Join-Path $preferences 'code-keybindings.json'
        $targetKeys = Join-Path $env:APPDATA 'Code\User\keybindings.json'
        if (Test-Path -LiteralPath $sourceKeys) {
            $keys = if (Test-Path $targetKeys) { @(Get-Content $targetKeys -Raw | ConvertFrom-Json -AsHashtable) } else { @() }
            $sourceBindings = @(Get-Content $sourceKeys -Raw | ConvertFrom-Json -AsHashtable)
            $keys = @(Merge-UniqueItems $keys $sourceBindings)
            Backup-File $targetKeys
            Write-Json $targetKeys $keys
        }
        if ($PowerlineFont) {
            $fontDir = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
            New-Item -ItemType Directory -Path $fontDir -Force | Out-Null
            $font = Get-Item -LiteralPath $PowerlineFont
            Copy-Item -LiteralPath $font.FullName -Destination (Join-Path $fontDir $font.Name) -Force
            $fontRegistry = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
            New-Item -Path $fontRegistry -Force | Out-Null
            New-ItemProperty -Path $fontRegistry -Name "$($terminalProfile.font.face) (TrueType)" -Value (Join-Path $fontDir $font.Name) -PropertyType String -Force | Out-Null
        }
        Write-Host 'Configuration merged. Restart WSL when other distributions can be stopped; then test corporate VPN/DNS.'
    }
    'Export' {
        if (-not $ExportPath -or (Test-Path -LiteralPath $ExportPath)) { throw 'Supply a new ExportPath on an encrypted disk; export contains secrets.' }
        Invoke-Native 'wsl.exe' @('--terminate', $Distro)
        Invoke-Native 'wsl.exe' @('--export', $Distro, $ExportPath)
        Get-FileHash -LiteralPath $ExportPath -Algorithm SHA256
        Write-Host 'This export excludes Windows files and Docker Desktop storage. Keep it encrypted.'
    }
}
