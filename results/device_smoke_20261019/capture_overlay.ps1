param([string]$Name = '10_whatsapp_overlay')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$frame = Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'overlay_frame.json') | ConvertFrom-Json
$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
$startInfo.Arguments = '-s 192.168.1.36:34679 exec-out screencap -p'
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.RedirectStandardOutput = $true
$process = [System.Diagnostics.Process]::Start($startInfo)
$buffer = New-Object System.IO.MemoryStream
try {
    $process.StandardOutput.BaseStream.CopyTo($buffer)
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw 'Screenshot capture failed' }
    $buffer.Position = 0
    $bitmap = [System.Drawing.Bitmap]::FromStream($buffer)
    try {
        $rect = New-Object System.Drawing.Rectangle([int]$frame[0], [int]$frame[1], [int]($frame[2] - $frame[0]), [int]($frame[3] - $frame[1]))
        $crop = $bitmap.Clone($rect, $bitmap.PixelFormat)
        try { $crop.Save((Join-Path $PSScriptRoot ($Name + '.png')), [System.Drawing.Imaging.ImageFormat]::Png) }
        finally { $crop.Dispose() }
    } finally { $bitmap.Dispose() }
} finally { $buffer.Dispose(); $process.Dispose() }
