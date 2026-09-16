param(
  [switch]$SkipDownload
)

$ErrorActionPreference = 'Stop'
$StatePath = Join-Path $PSScriptRoot 'constellation-rtl-driver-repair-state.json'
$TargetPattern = 'VID_0BDA&PID_2838&MI_00'
$OtherPattern = 'VID_0BDA&PID_2838&MI_01'
$PackageUrl = 'https://github.com/Timocop/libwdi-wdi-releases/releases/download/v1.0/x64.zip'
$WorkDir = Join-Path $env:TEMP 'UNG-CONSTELLATION-rtl-driver-repair'
$ZipPath = Join-Path $WorkDir 'libwdi-x64.zip'
$ExtractDir = Join-Path $WorkDir 'libwdi-x64'

function Get-InterfaceState([string]$Pattern) {
  $dev = Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match $Pattern } | Select-Object -First 1
  if (-not $dev) { return $null }

  $props = @{}
  foreach ($key in @('DEVPKEY_Device_DriverInfPath','DEVPKEY_Device_Service','DEVPKEY_Device_DriverProvider')) {
    try {
      $props[$key] = (Get-PnpDeviceProperty -InstanceId $dev.InstanceId -KeyName $key).Data
    } catch {
      $props[$key] = $null
    }
  }

  [ordered]@{
    instance_id = $dev.InstanceId
    friendly_name = $dev.FriendlyName
    status = [string]$dev.Status
    inf = $props['DEVPKEY_Device_DriverInfPath']
    service = $props['DEVPKEY_Device_Service']
    provider = $props['DEVPKEY_Device_DriverProvider']
  }
}

function Save-State($State) {
  $State | ConvertTo-Json -Depth 8 | Set-Content -Path $StatePath -Encoding UTF8
}

# Elevate once; do not touch any driver until running as administrator.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  $arg = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $PSCommandPath
  Start-Process powershell.exe -Verb RunAs -ArgumentList $arg
  exit 0
}

$before0 = Get-InterfaceState $TargetPattern
$before1 = Get-InterfaceState $OtherPattern
$state = [ordered]@{
  ok = $false
  receive_only = $true
  target = 'USB\\VID_0BDA&PID_2838&MI_00'
  action = 'bind WinUSB to RTL-SDR interface 0 only'
  interface0_before = $before0
  interface1_before = $before1
  package_url = $PackageUrl
  installer = 'wdi-simple.exe'
}

if (-not $before0) {
  $state.error = 'RTL-SDR interface 0 was not found.'
  Save-State $state
  Write-Host 'RTL-SDR interface 0 was not found.' -ForegroundColor Red
  exit 2
}

if ($before0.service -eq 'WinUSB') {
  $state.ok = $true
  $state.already_repaired = $true
  $state.interface0_after = $before0
  $state.interface1_after = $before1
  Save-State $state
  Write-Host 'Interface 0 is already using WinUSB.' -ForegroundColor Green
  exit 0
}

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
if (-not $SkipDownload) {
  Write-Host 'Downloading pinned libwdi command-line package...'
  Invoke-WebRequest -UseBasicParsing -Uri $PackageUrl -OutFile $ZipPath
}
if (-not (Test-Path $ZipPath)) {
  $state.error = "Required package is missing: $ZipPath"
  Save-State $state
  throw $state.error
}

if (Test-Path $ExtractDir) { Remove-Item $ExtractDir -Recurse -Force }
Expand-Archive -Path $ZipPath -DestinationPath $ExtractDir -Force
$wdi = Get-ChildItem $ExtractDir -Recurse -Filter 'wdi-simple.exe' | Select-Object -First 1
if (-not $wdi) {
  $state.error = 'wdi-simple.exe was not found in the pinned package.'
  Save-State $state
  throw $state.error
}

# Exact device target: Realtek RTL2832U, composite interface 0 only.
# --type 0 = WinUSB. No delete/remove/disable operation is used.
$args = @(
  '--name', 'RTL-SDR Interface 0',
  '--vid', '0x0BDA',
  '--pid', '0x2838',
  '--iid', '0',
  '--type', '0',
  '--inf', 'rtl-sdr-mi00-winusb.inf',
  '--timeout', '120000'
)

Write-Host 'Installing WinUSB on RTL-SDR interface 0 only...'
$proc = Start-Process -FilePath $wdi.FullName -ArgumentList $args -Wait -PassThru
$state.wdi_exit_code = $proc.ExitCode
Start-Sleep -Seconds 2

$after0 = Get-InterfaceState $TargetPattern
$after1 = Get-InterfaceState $OtherPattern
$state.interface0_after = $after0
$state.interface1_after = $after1
$state.interface1_unchanged = ($before1.service -eq $after1.service -and $before1.inf -eq $after1.inf)
$state.ok = ($after0 -and $after0.service -eq 'WinUSB' -and $state.interface1_unchanged)

if (-not $state.ok) {
  $state.error = 'WinUSB repair did not verify. No driver was deleted; inspect the state file before any further change.'
}
Save-State $state

if ($state.ok) {
  Write-Host 'SUCCESS: Interface 0 is now WinUSB and Interface 1 was left unchanged.' -ForegroundColor Green
  Write-Host "State file: $StatePath"
  $diagnostic = Join-Path $PSScriptRoot 'run-windows-rtl-sdr.cmd'
  if (Test-Path $diagnostic) {
    Write-Host 'Running CONSTELLATION RTL-SDR hardware diagnostic...'
    & $diagnostic
  }
  exit 0
}

Write-Host 'Repair did not verify. Nothing was deleted.' -ForegroundColor Red
Write-Host "State file: $StatePath"
exit 3
