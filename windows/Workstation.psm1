Set-StrictMode -Version Latest

function Merge-JsonMap($Target, $Source) {
    foreach ($key in $Source.Keys) {
        if ($Target.Contains($key) -and $Target[$key] -is [Collections.IDictionary] -and $Source[$key] -is [Collections.IDictionary]) {
            Merge-JsonMap $Target[$key] $Source[$key]
        } else { $Target[$key] = $Source[$key] }
    }
}

function Merge-IniSettings([string[]]$Lines, $Settings) {
    foreach ($section in $Settings.Keys) {
        foreach ($key in $Settings[$section].Keys) {
            $foundSection = $false; $foundKey = $false; $active = $false
            $output = [Collections.Generic.List[string]]::new()
            foreach ($line in $Lines) {
                if ($line -match '^\s*\[([^]]+)\]') {
                    $nextSection = $Matches[1]
                    if ($active -and -not $foundKey) { $output.Add("$key=$($Settings[$section][$key])"); $foundKey = $true }
                    $active = $nextSection -eq $section
                    if ($active) { $foundSection = $true }
                }
                if ($active -and $line -match "^\s*$([regex]::Escape($key))\s*=") {
                    if (-not $foundKey) { $output.Add("$key=$($Settings[$section][$key])") }
                    $foundKey = $true
                } else { $output.Add($line) }
            }
            if (-not $foundSection) { $output.Add("[$section]") }
            if (-not $foundKey) { $output.Add("$key=$($Settings[$section][$key])") }
            $Lines = @($output)
        }
    }
    return $Lines
}

function Merge-UniqueItems([object[]]$Existing, [object[]]$Source) {
    $seen = [Collections.Generic.HashSet[string]]::new()
    foreach ($item in @($Existing) + @($Source)) {
        if ($null -ne $item -and $seen.Add(($item | ConvertTo-Json -Compress -Depth 100))) { Write-Output -NoEnumerate $item }
    }
}

function Merge-TerminalPreferences($Target, $Source, $terminalProfile, [string]$OldWindowsHome, [string]$NewWindowsHome) {
    # Keep target distro identities; import source visual settings and shortcuts.
    $selected = @($Source.profiles.list | Where-Object { $_.guid -eq $Source.defaultProfile })
    if ($selected.Count -eq 0) { $selected = @($Source.profiles.list | Where-Object { $_.name -eq 'Debian' }) }
    if ($selected.Count) {
        foreach ($key in $selected[0].Keys) {
            if ($key -notin @('guid', 'name', 'commandline', 'source', 'startingDirectory', 'hidden')) { $terminalProfile[$key] = $selected[0][$key] }
        }
        if ($terminalProfile.Contains('backgroundImage') -and $OldWindowsHome) {
            $terminalProfile.backgroundImage = $terminalProfile.backgroundImage.Replace($OldWindowsHome, $NewWindowsHome)
        }
    }
    foreach ($key in $Source.Keys) {
        if ($key -in @('profiles', 'defaultProfile', 'schemes', 'actions', 'keybindings', 'themes', '$schema', '$help')) { continue }
        $Target[$key] = $Source[$key]
    }
    foreach ($key in @('actions', 'keybindings')) {
        if (-not $Source.Contains($key)) { continue }
        $items = $Source[$key]
        if ($selected.Count) {
            # Remap shortcuts referencing the old default profile.
            $items = ConvertFrom-Json -AsHashtable -InputObject ((ConvertTo-Json -InputObject $items -Depth 100).Replace($selected[0].guid, $terminalProfile.guid))
        }
        $old = if ($Target.Contains($key)) { @($Target[$key]) } else { @() }
        $Target[$key] = @(Merge-UniqueItems $old @($items))
    }
    foreach ($key in @('schemes', 'themes')) {
        if (-not $Source.Contains($key)) { continue }
        $old = if ($Target.Contains($key)) { @($Target[$key]) } else { @() }
        $names = @($Source[$key] | ForEach-Object { $_.name })
        $Target[$key] = @($old | Where-Object { $_.name -notin $names }) + @($Source[$key])
    }
}

Export-ModuleMember -Function Merge-JsonMap, Merge-IniSettings, Merge-UniqueItems, Merge-TerminalPreferences
