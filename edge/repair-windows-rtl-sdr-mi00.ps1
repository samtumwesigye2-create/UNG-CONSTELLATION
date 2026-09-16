$ErrorActionPreference = 'Stop'

# UNG-CONSTELLATION targeted Windows repair for RTL-SDR composite Interface 0.
# This script deliberately never removes driver packages and never touches MI_01.
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

# The machine evidence showed MI_00 on REALTEK/oem23.inf and MI_01 on libwdi WinUSB/oem24.inf.
# A package generated for MI_01 cannot legally bind to MI_00. Do not force it and do not delete oem23.inf.
# Use libwdi's single-device installer when available; it generates a correctly matched, signed WinUSB package.
$wdiCandidates = @(
    (Join-Path $PSScriptRoot 'wdi-simple.exe'),
    (Join-Path $env:USERPROFILE 'Downloads\wdi-simple.exe')
)
$wdi = $wdiCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $wdi) {
    $state.error = 'MI_00 is still using the Realtek driver. A device-specific WinUSB package is required; wdi-simple.exe is not present, so no driver changes were made.'
    $state.required_tool = 'wdi-simple.exe (libwdi)'
    $state.current_service = $before.service
    $state.current_provider = $before.provider
    Save-State $state
    exit 12
}

$driverDir = Join-Path $PSScriptRoot 'generated-winusb-mi00'
New-Item -ItemType Directory -Force -Path $driverDir | Out-Null
$args = @(
    '--name', 'UNG-CONSTELLATION RTL-SDR Interface 0',
    '--vid', '0x0BDA',
    '--pid', '0x2838',
    '--iid', '0',
    '--type', '0',
    '--inf', 'ung-constellation-rtl-sdr-mi00.inf',
    '--dest', $driverDir,
    '--timeout', '120000'
)
$proc = Start-Process -FilePath $wdi -ArgumentList $args -Wait -PassThru
$state.installer_exit_code = $proc.ExitCode

Start-Sleep -Seconds 2
$device = Get-TargetDevice
if (-not $device) {
    $state.error = 'Driver installer returned, but RTL-SDR Interface 0 is no longer present.'
    Save-State $state
    exit 13
}
$after = Get-DriverState $device
$state.after = $after

if ($after.service -ne 'WinUSB') {
    $state.error = "Driver installation did not bind WinUSB to MI_00. Current service: $($after.service)."
    Save-State $state
    exit 14
}

$state.ok = $true
$state.action = 'installed_winusb_mi00'
$state.message = 'WinUSB is now bound to RTL-SDR Interface 0. MI_01 was not modified.'
Save-State $state
exit 0
