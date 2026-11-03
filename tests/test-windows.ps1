# Execute portable merge tests on Linux/Windows; never invoke provisioning.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '../windows/Workstation.psm1') -Force
function Assert-True($Value, [string]$Message) { if (-not $Value) { throw $Message } }

$inputLines = @('# preserve comment', '[wsl2]', 'memory=8GB', 'dnsTunneling=true', '[other]', 'custom=true')
$settings = @{wsl2 = @{dnsTunneling = 'false'; networkingMode = 'mirrored'}; experimental = @{hostAddressLoopback = 'true'}}
$once = @(Merge-IniSettings $inputLines $settings)
$twice = @(Merge-IniSettings $once $settings)
Assert-True (($once -join "`n") -eq ($twice -join "`n")) 'INI merge is not idempotent'
Assert-True ('memory=8GB' -in $once -and '# preserve comment' -in $once -and 'custom=true' -in $once) 'Unmanaged INI keys lost'
Assert-True (@($once | Where-Object { $_ -eq 'dnsTunneling=false' }).Count -eq 1) 'INI key duplicated'
$map = [ordered]@{theme = 'old'; nested = @{keep = 1; replace = 1}}
Merge-JsonMap $map @{theme = 'new'; nested = @{replace = 2}}
Assert-True ($map.theme -eq 'new' -and $map.nested.keep -eq 1 -and $map.nested.replace -eq 2) 'Settings map merge failed'
$binding = @{key = 'ctrl+a'; command = 'example'}
$bindings = @(Merge-UniqueItems @($binding) @($binding))
Assert-True ($bindings.Count -eq 1) 'Bindings duplicated'
$target = @{profiles = @{list = @(@{guid = 'keep'; name = 'existing'})}; schemes = @(@{name = 'existing'})}
$source = @{defaultProfile = 'old'; profiles = @{list = @(@{guid = 'old'; name = 'Debian'; font = @{face = 'Powerline'}; backgroundImage = 'C:\Users\old\image.png'})}; actions = @(@{profile = 'old'}); schemes = @(@{name = 'custom'}); copyOnSelect = $true}
$terminalProfile = @{guid = 'new'; name = 'new distro'; commandline = 'wsl -d new'}
Merge-TerminalPreferences $target $source $terminalProfile 'C:\Users\old' 'C:\Users\new'
Merge-TerminalPreferences $target $source $terminalProfile 'C:\Users\old' 'C:\Users\new'
Assert-True ($target.profiles.list[0].guid -eq 'keep' -and $terminalProfile.guid -eq 'new') 'Distro identities overwritten'
Assert-True ($terminalProfile.backgroundImage -eq 'C:\Users\new\image.png') 'Background path not relocated'
Assert-True ($target.actions.Count -eq 1 -and $target.actions[0].profile -eq 'new') 'Actions duplicated or profile GUID not remapped'
Assert-True ($target.schemes.Count -eq 2 -and $target.copyOnSelect) 'Terminal preferences lost'
Write-Host 'PowerShell merge tests passed.'
