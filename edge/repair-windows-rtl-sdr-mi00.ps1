$ErrorActionPreference = 'Stop'

# UNG-CONSTELLATION targeted Windows repair for RTL-SDR composite Interface 0.
# It never deletes driver packages and only prepares the confirmed MI_00 target.
$targetId = 'VID_0BDA&PID_2838&MI_00'
$statePath = Join-Path $PSScriptRoot 'constellation-windows-rtl-sdr-driver-state.json'

function Save-State([hashtable]$state) {
    $state | ConvertTo-Json -Depth 5 | Set-Content -Path $statePath -Encoding UTF8
    $state | ConvertTo-Json -Depth 5
}

function Get-TargetDevice {
    @(Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -match $targetId }) | Select-Object -First 1
}

function Get-DriverState($device) {
    $service = (Get-PnpDeviceProperty -InstanceId $device.InstanceId -KeyName 'DEVPKEY_Device_Service' -ErrorAction SilentlyContinue).Data
    $provider = (Get-PnpDeviceProperty -InstanceId $device.InstanceId -KeyName 'DEVPKEY_Device_DriverProvider' -ErrorAction SilentlyContinue).Data
    $inf = (Get-PnpDeviceProperty -InstanceId $device.InstanceId -KeyName 'DEVPKEY_Device_DriverInfPath' -ErrorAction SilentlyContinue).Data
    return @{ service = $service; provider = $provider; inf = $inf }
}

$state = @{
    ok = $false
    target = 'USB\VID_0BDA&PID_2838&MI_00'
    receive_only = $true
    timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $state.error = 'Administrator privileges are required for USB driver repair.'
    Save-State $state
    exit 10
}

$device = Get-TargetDevice
if (-not $device) {
    $state.error = 'RTL-SDR Interface 0 was not found. Keep the receiver plugged in and retry.'
    Save-State $state
    exit 11
}

$state.instance_id = $device.InstanceId
$before = Get-DriverState $device
$state.before = $before
if ($before.service -eq 'WinUSB') {
    $state.ok = $true
    $state.action = 'none'
    $state.message = 'RTL-SDR Interface 0 is already using WinUSB.'
    Save-State $state
    exit 0
}

# The official libwdi/Zadig tool already on this PC can generate and sign the
# device-specific WinUSB package. Prepare an exact preset so the wrong USB
# interface cannot be selected by accident.
$downloads = Join-Path $env:USERPROFILE 'Downloads'
$zadig = Get-ChildItem -Path $downloads -Filter 'zadig*.exe' -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $zadig) {
    $state.error = 'Official Zadig executable was not found in Downloads. No driver changes were made.'
    Save-State $state
    exit 12
}

$preset = Join-Path $PSScriptRoot 'UNG-CONSTELLATION-RTL-SDR-MI00.cfg'
@'
[device]
Description = "UNG-CONSTELLATION RTL-SDR Interface 0"
VID = 0x0BDA
PID = 0x2838
MI = 0x00
'@ | Set-Content -Path $preset -Encoding ASCII

$ini = Join-Path $zadig.DirectoryName 'zadig.ini'
@'
[general]
advanced_mode = true
exit_on_success = false
log_level = 0

[device]
list_all = true
include_hubs = false
trim_whitespaces = true

[driver]
default_driver = 0
extract_only = false
'@ | Set-Content -Path $ini -Encoding ASCII

$state.action = 'preset_prepared'
$state.preset = $preset
$state.zadig = $zadig.FullName
$state.message = 'Exact MI_00 preset prepared. In Zadig use Device > Load Preset Device, choose UNG-CONSTELLATION-RTL-SDR-MI00.cfg, confirm WinUSB, then Install/Replace Driver.'
Save-State $state

Start-Process -FilePath $zadig.FullName -Verb RunAs
Write-Host ''
Write-Host 'UNG-CONSTELLATION DRIVER REPAIR' -ForegroundColor Cyan
Write-Host 'Target locked to: USB VID 0BDA / PID 2838 / MI 00'
Write-Host "Preset: $preset"
Write-Host 'In Zadig: Device > Load Preset Device > select that preset > confirm WinUSB > Install/Replace Driver.' -ForegroundColor Yellow
Write-Host 'Do NOT select the composite parent or any other interface.' -ForegroundColor Yellow
exit 20
