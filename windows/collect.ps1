#Requires -Version 7.2
param([Parameter(Mandatory)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Choose a new private output directory.' }
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
# Limit access to the current Windows user and SYSTEM.
& icacls.exe $OutputDirectory /inheritance:r /grant:r "${env:USERDOMAIN}\${env:USERNAME}:(OI)(CI)F" 'SYSTEM:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Cannot restrict inventory permissions' }
& wsl.exe --version | Set-Content (Join-Path $OutputDirectory 'wsl-version.txt')
& wsl.exe --list --verbose | Set-Content (Join-Path $OutputDirectory 'distributions.txt')
Get-ComputerInfo -Property WindowsProductName, WindowsVersion, OsBuildNumber, OsArchitecture |
    ConvertTo-Json | Set-Content (Join-Path $OutputDirectory 'windows.json')
& winget.exe export --output (Join-Path $OutputDirectory 'winget.json') --include-versions --accept-source-agreements
if ($LASTEXITCODE -ne 0) { throw 'winget export failed' }
if (Get-Command code.cmd -ErrorAction SilentlyContinue) {
    & code.cmd --list-extensions --show-versions | Set-Content (Join-Path $OutputDirectory 'vscode-extensions.txt')
}
Write-Host 'Private inventory written. Review before sharing; no credentials were exported.'
