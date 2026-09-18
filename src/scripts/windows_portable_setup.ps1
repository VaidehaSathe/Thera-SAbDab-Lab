param(
    [switch]$NoLaunch,
    [switch]$IncludeBuildTools,
    [switch]$ForceRepair
)
$target = Join-Path $PSScriptRoot 'windows_system_python_setup.ps1'
$argsList = @()
if($NoLaunch){ $argsList += '-NoLaunch' }
if($IncludeBuildTools){ $argsList += '-IncludeBuildTools' }
if($ForceRepair){ $argsList += '-ForceRepair' }
& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $target @argsList
exit $LASTEXITCODE
