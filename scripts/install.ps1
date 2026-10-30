#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$ProjectPath = ".",
    [int]$Port = 3000,
    [switch]$SkipPortCheck
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ProjectPath)) {
    throw "Project path not found: $ProjectPath"
}
$project = (Resolve-Path -LiteralPath $ProjectPath).Path
$projectFile = Join-Path $project "project.godot"
$pluginCfg = Join-Path $project "addons\godot_mcp\plugin.cfg"

Write-Host "Project: $project"
if (-not (Test-Path -LiteralPath $projectFile)) {
    throw "project.godot not found in $project"
}
if (-not (Test-Path -LiteralPath $pluginCfg)) {
    throw "addons\godot_mcp\plugin.cfg not found. Copy the upstream addon into the project first."
}

$version = "unknown"
$cfgText = Get-Content -LiteralPath $pluginCfg -Raw
if ($cfgText -match 'version\s*=\s*"([^"]+)"') {
    $version = $matches[1]
}
Write-Host "Addon:   $pluginCfg (version $version)"

$pluginPath = "res://addons/godot_mcp/plugin.cfg"
$lines = Get-Content -LiteralPath $projectFile
$inEditorPlugins = $false
$enabledLine = $null
foreach ($line in $lines) {
    if ($line -match '^\s*\[([^\]]+)\]\s*$') {
        $inEditorPlugins = ($matches[1] -eq "editor_plugins")
        continue
    }
    if ($inEditorPlugins -and $line -match '^\s*enabled\s*=') {
        $enabledLine = $line
        break
    }
}

if ($enabledLine -and $enabledLine.Contains($pluginPath)) {
    Write-Host "Enabled: yes ($enabledLine)"
}
else {
    Write-Warning "Plugin is not enabled in project.godot."
    Write-Host ""
    Write-Host "Add this section to project.godot (or enable it in Project Settings > Plugins):"
    Write-Host ""
    Write-Host "  [editor_plugins]"
    Write-Host ('  enabled=PackedStringArray("' + $pluginPath + '")')
    Write-Host ""
}

function Test-TcpPort {
    param([string]$HostName, [int]$PortNumber)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $task = $client.ConnectAsync($HostName, $PortNumber)
        if (-not $task.Wait(800)) {
            return $false
        }
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

if (-not $SkipPortCheck) {
    if (Test-TcpPort "127.0.0.1" $Port) {
        Write-Host "Port ${Port}: listening"
    }
    else {
        Write-Warning "Port $Port is not listening. Open the project in the Godot editor (with -e) and enable the plugin."
    }
}

$entry = [ordered]@{
    godot = [ordered]@{
        type = "http"
        url  = "http://127.0.0.1:$Port/mcp"
    }
}

Write-Host ""
Write-Host 'Add this under "mcpServers" in %USERPROFILE%\.qoder-cn\settings.json:'
$entry | ConvertTo-Json -Depth 6

Write-Host ""
Write-Host "Open the editor with:"
Write-Host ('  & "<Godot exe>" -e --path "' + $project + '"')
Write-Host "Then restart Qoder or open a new session, and verify with: python scripts/probe_godot_mcp.py"
