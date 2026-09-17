$ErrorActionPreference = 'Stop'

# UNG-CONSTELLATION targeted Windows repair for RTL-SDR composite Interface 0.
# It never deletes driver packages and only prepares the confirmed MI_00 target.
$targetId = 'VID_0BDA&PID_2838&MI_00'
$statePath = Join-Path $PSScriptRoot 'constellation-windows-rtl-sdr-driver-state.json'

function Save-State([hashtable]$state) {
    $state | ConvertTo-Json -Depth 5 | Set-Content -Path $statePath -Encoding UTF8
    $state | ConvertTo-Json -Depth 5
}

function Get-TargetDevices {
    @(Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object {
        $_.InstanceId -match '^USB\\VID_0BDA&PID_2838&MI_00\\'
    })
}

function Get-DriverState($device) {
    $service = (Get-PnpDeviceProperty -InstanceId $device.InstanceId -KeyName 'DEVPKEY_Device_Service' -ErrorAction SilentlyContinue).Data
    $provider = (Get-PnpDeviceProperty -InstanceId $device.InstanceId -KeyName 'DEVPKEY_Device_DriverProvider' -ErrorAction SilentlyContinue).Data
    $inf = (Get-PnpDeviceProperty -InstanceId $device.InstanceId -KeyName 'DEVPKEY_Device_DriverInfPath' -ErrorAction SilentlyContinue).Data
    return @{ service = $service; provider = $provider; inf = $inf }
}

function Get-Interface1State {
    @(
        Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
            Where-Object { $_.InstanceId -match '^USB\\VID_0BDA&PID_2838&MI_01\\' } |
            ForEach-Object {
                $driver = Get-DriverState $_
                "{0}|{1}|{2}|{3}" -f $_.InstanceId, $driver.service, $driver.provider, $driver.inf
            } | Sort-Object
    )
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

$devices = @(Get-TargetDevices)
if ($devices.Count -eq 0) {
    $state.error = 'RTL-SDR Interface 0 was not found. Keep the receiver plugged in and retry.'
    Save-State $state
    exit 11
}
if ($devices.Count -ne 1) {
    $state.error = 'Multiple RTL-SDR Interface 0 devices are attached. Leave only the intended receiver plugged in.'
    Save-State $state
    exit 13
}
$device = $devices[0]

$state.instance_id = $device.InstanceId
$before = Get-DriverState $device
$state.before = $before
$interface1Before = @(Get-Interface1State)
if ($before.service -eq 'WinUSB') {
    $state.ok = $true
    $state.action = 'none'
    $state.message = 'RTL-SDR Interface 0 is already using WinUSB.'
    Save-State $state
    exit 0
}
if ($before.service -ne 'RTL2832UUSB') {
    $state.error = 'Interface 0 is not using the expected Realtek driver. No changes were made.'
    Save-State $state
    exit 14
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
$signature = Get-AuthenticodeSignature -FilePath $zadig.FullName
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Akeo Consulting') {
    $state.error = 'Zadig in Downloads does not have a valid Akeo Consulting signature. No changes were made.'
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

$state.action = 'preset_prepared'
$state.preset = $preset
$state.zadig = $zadig.FullName
$state.message = 'Exact MI_00 preset prepared. In Zadig use Device > Load Preset Device, choose UNG-CONSTELLATION-RTL-SDR-MI00.cfg, confirm WinUSB, then Install/Replace Driver.'
Save-State $state

Write-Host ''
Write-Host 'UNG-CONSTELLATION DRIVER REPAIR' -ForegroundColor Cyan
Write-Host 'Target locked to: USB VID 0BDA / PID 2838 / MI 00'
Write-Host "Preset: $preset"
Write-Host 'In Zadig: Device > Load Preset Device > select that preset > confirm WinUSB > Install/Replace Driver, then close Zadig.' -ForegroundColor Yellow
Write-Host 'Do NOT select the composite parent or any other interface.' -ForegroundColor Yellow
Start-Process -FilePath $zadig.FullName -Verb RunAs -Wait -PassThru | Out-Null

$deviceAfter = @(Get-TargetDevices | Where-Object { $_.InstanceId -eq $device.InstanceId }) | Select-Object -First 1
if (-not $deviceAfter) {
    $state.error = 'Interface 0 disappeared after Zadig closed. Reconnect the dongle and retry.'
    Save-State $state
    exit 15
}
$after = Get-DriverState $deviceAfter
$state.after = $after
$interface1After = @(Get-Interface1State)
if ((Compare-Object $interface1Before $interface1After) -ne $null) {
    $state.error = 'Interface 1 changed during repair. Stop and inspect the Windows device drivers.'
    Save-State $state
    exit 16
}
if ($after.service -ne 'WinUSB') {
    $state.error = 'Interface 0 is still not bound to WinUSB. The driver repair did not complete.'
    Save-State $state
    exit 17
}

$diagnostic = Join-Path $PSScriptRoot 'windows-rtl-sdr-edge.ps1'
$check = Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$diagnostic`"") -Wait -PassThru
$state.diagnostic_exit_code = $check.ExitCode
if ($check.ExitCode -ne 0) {
    $state.error = 'WinUSB is bound to Interface 0, but the receive-only RTL-SDR diagnostic failed. See constellation-windows-rtl-sdr-state.json.'
    Save-State $state
    exit 18
}
$state.ok = $true
$state.action = 'driver_replaced_and_verified'
$state.message = 'Interface 0 uses WinUSB, Interface 1 is unchanged, and the receive-only diagnostic passed.'
Save-State $state
exit 0
