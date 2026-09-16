$ErrorActionPreference = 'Stop'

# UNG-CONSTELLATION Windows RTL-SDR receive-only hardware diagnostic.
# Uses the rtlsdr.dll already present in an SDR++ installation/download.

$statePath = Join-Path $PSScriptRoot 'constellation-windows-rtl-sdr-state.json'
$centerHz = 137900000
$sampleRate = 1024000
$sampleCount = 262144

function Write-State($obj) {
    $obj | ConvertTo-Json -Depth 6 | Set-Content -Path $statePath -Encoding UTF8
    $obj | ConvertTo-Json -Depth 6
}

function Find-RtlSdrDll {
    $candidates = @(
        (Join-Path $PSScriptRoot 'rtlsdr.dll'),
        (Join-Path $env:USERPROFILE 'Downloads\sdrpp_windows_x64\sdrpp_windows_x64\rtlsdr.dll'),
        (Join-Path $env:USERPROFILE 'Downloads\sdrpp_windows_x64\rtlsdr.dll')
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return (Resolve-Path $p).Path }
    }
    $downloads = Join-Path $env:USERPROFILE 'Downloads'
    if (Test-Path $downloads) {
        $found = Get-ChildItem -Path $downloads -Filter 'rtlsdr.dll' -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    return $null
}

$baseState = [ordered]@{
    ok = $false
    receive_only = $true
    timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    center_hz = $centerHz
    sample_rate = $sampleRate
}

try {
    $dll = Find-RtlSdrDll
    if (-not $dll) {
        $baseState.error = 'rtlsdr.dll not found. Keep the extracted SDR++ folder in Downloads and run this diagnostic again.'
        Write-State $baseState
        exit 1
    }
    $baseState.rtlsdr_dll = $dll

    $nativeDir = Split-Path -Parent $dll
    $env:PATH = "$nativeDir;$env:PATH"

    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RtlSdrNative {
    [DllImport("rtlsdr.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern UInt32 rtlsdr_get_device_count();

    [DllImport("rtlsdr.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern IntPtr rtlsdr_get_device_name(UInt32 index);

    [DllImport("rtlsdr.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern int rtlsdr_open(out IntPtr dev, UInt32 index);

    [DllImport("rtlsdr.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern int rtlsdr_close(IntPtr dev);

    [DllImport("rtlsdr.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern int rtlsdr_set_center_freq(IntPtr dev, UInt32 freq);

    [DllImport("rtlsdr.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern int rtlsdr_set_sample_rate(IntPtr dev, UInt32 rate);

    [DllImport("rtlsdr.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern int rtlsdr_reset_buffer(IntPtr dev);

    [DllImport("rtlsdr.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern int rtlsdr_read_sync(IntPtr dev, byte[] buf, int len, out int n_read);
}
"@

    $count = [RtlSdrNative]::rtlsdr_get_device_count()
    $baseState.device_count = [int]$count
    if ($count -lt 1) {
        $baseState.error = 'rtlsdr.dll loaded, but no RTL-SDR device was found.'
        Write-State $baseState
        exit 2
    }

    $namePtr = [RtlSdrNative]::rtlsdr_get_device_name(0)
    $baseState.device = [Runtime.InteropServices.Marshal]::PtrToStringAnsi($namePtr)

    $dev = [IntPtr]::Zero
    $rc = [RtlSdrNative]::rtlsdr_open([ref]$dev, 0)
    $baseState.open_returncode = $rc
    if ($rc -ne 0 -or $dev -eq [IntPtr]::Zero) {
        $baseState.error = 'RTL-SDR was detected but could not be opened. Another application may have it open, or the WinUSB interface is not available.'
        Write-State $baseState
        exit 3
    }

    try {
        $freqRc = [RtlSdrNative]::rtlsdr_set_center_freq($dev, [uint32]$centerHz)
        $rateRc = [RtlSdrNative]::rtlsdr_set_sample_rate($dev, [uint32]$sampleRate)
        $resetRc = [RtlSdrNative]::rtlsdr_reset_buffer($dev)
        $buf = New-Object byte[] $sampleCount
        $nRead = 0
        $readRc = [RtlSdrNative]::rtlsdr_read_sync($dev, $buf, $buf.Length, [ref]$nRead)

        $baseState.set_frequency_returncode = $freqRc
        $baseState.set_sample_rate_returncode = $rateRc
        $baseState.reset_buffer_returncode = $resetRc
        $baseState.read_returncode = $readRc
        $baseState.bytes_read = $nRead

        if ($readRc -ne 0 -or $nRead -le 0) {
            $baseState.error = 'RTL-SDR opened, but no IQ samples were returned.'
            Write-State $baseState
            exit 4
        }

        $slice = if ($nRead -lt $buf.Length) { $buf[0..($nRead-1)] } else { $buf }
        $min = 255
        $max = 0
        [double]$sum = 0
        [double]$sumSq = 0
        foreach ($b in $slice) {
            if ($b -lt $min) { $min = $b }
            if ($b -gt $max) { $max = $b }
            $sum += $b
            $sumSq += ($b * $b)
        }
        $mean = $sum / $nRead
        $variance = ($sumSq / $nRead) - ($mean * $mean)

        $baseState.sample_min = $min
        $baseState.sample_max = $max
        $baseState.sample_mean = [Math]::Round($mean, 3)
        $baseState.sample_variance = [Math]::Round($variance, 3)
        $baseState.ok = $true
        Write-State $baseState
        exit 0
    }
    finally {
        if ($dev -ne [IntPtr]::Zero) { [void][RtlSdrNative]::rtlsdr_close($dev) }
    }
}
catch {
    $baseState.error = $_.Exception.Message
    Write-State $baseState
    exit 10
}
