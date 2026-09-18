$ErrorActionPreference='Continue'
$PackageRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if($env:LOCALAPPDATA){ $Base=Join-Path $env:LOCALAPPDATA 'TSCurator' } else { $Base=Join-Path $env:TEMP 'TSCurator' }
$Venv=Join-Path $Base 'venv104'
$Py=Join-Path $Venv 'Scripts\python.exe'
$Log=Join-Path $Base 'logs\windows_launcher_v104.log'
$Crash=Join-Path $Base 'logs\app_crash.log'
$Report=Join-Path $Base 'logs\diagnostic_report_v104.txt'

$lines = New-Object System.Collections.Generic.List[string]
function Add-Line([string]$s){ $lines.Add($s); Write-Host $s }

Add-Line 'Thera-SAbDab WHO INN Curator - Windows diagnostics v1.0.4'
Add-Line ('Package root: ' + $PackageRoot)
Add-Line ('Windows: ' + [Environment]::OSVersion.VersionString)
Add-Line ('64-bit OS: ' + [Environment]::Is64BitOperatingSystem)
Add-Line ('Private venv: ' + $Venv)
Add-Line ('Private venv Python exists: ' + (Test-Path $Py))
Add-Line ('Launcher log: ' + $Log)
Add-Line ''

$pyLauncher=Get-Command py.exe -ErrorAction SilentlyContinue
if($pyLauncher){
    Add-Line ('py.exe: ' + $pyLauncher.Source)
    $out=& $pyLauncher.Source -0p 2>&1 | Out-String
    Add-Line $out.Trim()
}else{ Add-Line 'py.exe: not found' }

$pythonCmd=Get-Command python.exe -ErrorAction SilentlyContinue
if($pythonCmd){
    Add-Line ('python.exe on PATH: ' + $pythonCmd.Source)
    $out=& $pythonCmd.Source -c "import sys,struct; print(sys.version); print(sys.executable); print('bits',struct.calcsize('P')*8)" 2>&1 | Out-String
    Add-Line $out.Trim()
}else{ Add-Line 'python.exe on PATH: not found' }

Add-Line ''
if(Test-Path $Py){
    $v=& $Py --version 2>&1 | Out-String; Add-Line $v.Trim()
    $q=& $Py -c "import sys; print(sys.executable); from PyQt5 import QtCore; print('Qt',QtCore.QT_VERSION_STR,'PyQt',QtCore.PYQT_VERSION_STR)" 2>&1 | Out-String; Add-Line $q.Trim()
    Push-Location $PackageRoot
    $env:PYTHONPATH=$PackageRoot
    $a=& $Py -c "from thera_curator.db import Database; from thera_curator.qt_compat import BINDING; d=Database(); print('Application imports OK; binding=',BINDING,'records=',d.count_records()); d.close()" 2>&1 | Out-String
    Pop-Location
    Add-Line $a.Trim()
}

$t=Join-Path $PackageRoot 'vendor\tesseract\tesseract.exe'
$p1=Join-Path $PackageRoot 'vendor\poppler\Library\bin\pdftoppm.exe'
$p2=Join-Path $PackageRoot 'vendor\poppler\bin\pdftoppm.exe'
Add-Line ('Bundled Tesseract: ' + (Test-Path $t))
Add-Line ('Bundled pdftoppm: ' + ((Test-Path $p1) -or (Test-Path $p2)))
Add-Line ''

if(Test-Path $Log){ Add-Line '--- Last 80 launcher log lines ---'; Get-Content -LiteralPath $Log -Tail 80 | ForEach-Object { Add-Line $_ } }
if(Test-Path $Crash){ Add-Line ''; Add-Line '--- Application crash log ---'; Get-Content -LiteralPath $Crash -Tail 120 | ForEach-Object { Add-Line $_ } }

$lines | Set-Content -LiteralPath $Report -Encoding UTF8
Add-Line ''
Add-Line ('Diagnostic report written to: ' + $Report)
