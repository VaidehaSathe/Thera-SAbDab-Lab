param(
    [switch]$NoLaunch,
    [switch]$IncludeBuildTools,
    [switch]$ForceRepair
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$PackageRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $PackageRoot

if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'This release requires 64-bit Windows 10 or Windows 11.'
}

if ($env:LOCALAPPDATA) {
    $LocalBase = Join-Path $env:LOCALAPPDATA 'TSCurator'
} elseif ($env:TEMP) {
    $LocalBase = Join-Path $env:TEMP 'TSCurator'
} else {
    throw 'Neither LOCALAPPDATA nor TEMP is available.'
}

$Venv = Join-Path $LocalBase 'venv104'
$Cache = Join-Path $LocalBase 'cache104'
$PipCache = Join-Path $Cache 'pip'
$LogDir = Join-Path $LocalBase 'logs'
$LogFile = Join-Path $LogDir 'windows_launcher_v104.log'
$CrashLog = Join-Path $LogDir 'app_crash.log'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
$VenvPythonW = Join-Path $Venv 'Scripts\pythonw.exe'

New-Item -ItemType Directory -Force -Path $LocalBase,$Cache,$PipCache,$LogDir | Out-Null

function Write-Log([string]$Message) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[$stamp] $Message"
    Write-Host $line
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

function Test-PythonCandidate([string]$Command, [string[]]$PrefixArgs) {
    try {
        $cmdInfo = Get-Command $Command -ErrorAction SilentlyContinue
        if (-not $cmdInfo) { return $null }
        $probe = @'
import sys, struct
print(sys.executable)
print(str(sys.version_info.major) + '.' + str(sys.version_info.minor))
print(struct.calcsize('P') * 8)
'@
        $out = & $cmdInfo.Source @PrefixArgs -c $probe 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $out -or $out.Count -lt 3) { return $null }
        $exe = [string]$out[0]
        $ver = [string]$out[1]
        $bits = [string]$out[2]
        if ($bits.Trim() -ne '64') { return $null }
        return [PSCustomObject]@{ Exe = $exe.Trim(); Version = $ver.Trim(); Command = $cmdInfo.Source; PrefixArgs = $PrefixArgs }
    } catch {
        return $null
    }
}

function Find-SystemPython {
    # Prefer versions with the broadest wheel support for the pinned Windows dependencies.
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        foreach ($tag in @('-3.11','-3.12','-3.13','-3.10','-3.14')) {
            $p = Test-PythonCandidate $py.Source @($tag)
            if ($p) { return $p }
        }
    }

    foreach ($name in @('python.exe','python3.exe','python')) {
        $p = Test-PythonCandidate $name @()
        if ($p) { return $p }
    }

    # Common per-user install locations, useful when PATH/py launcher is missing.
    $roots = @()
    if ($env:LOCALAPPDATA) { $roots += (Join-Path $env:LOCALAPPDATA 'Programs\Python') }
    if ($env:ProgramFiles) { $roots += (Join-Path $env:ProgramFiles 'Python*') }
    foreach ($rootPattern in $roots) {
        foreach ($candidate in (Get-ChildItem -Path $rootPattern -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending)) {
            $exe = Join-Path $candidate.FullName 'python.exe'
            if (Test-Path $exe) {
                $p = Test-PythonCandidate $exe @()
                if ($p) { return $p }
            }
        }
    }
    return $null
}

Write-Log "Package root: $PackageRoot"
Write-Log "Private venv: $Venv"
Write-Log "Launcher log: $LogFile"

$SystemPython = Find-SystemPython
if (-not $SystemPython) {
    throw @'
No usable 64-bit Python installation was found.
This v1.0.4 launcher intentionally uses the Python already installed on your PC instead of downloading another Python runtime.
Install 64-bit Python 3.11, 3.12 or 3.13 from python.org with the Python launcher enabled, then run START_APP.bat again.
'@
}

Write-Log ("Using installed Python {0}: {1}" -f $SystemPython.Version, $SystemPython.Exe)

if ($ForceRepair -and (Test-Path $Venv)) {
    Write-Log 'ForceRepair requested; deleting the private v1.0.4 virtual environment.'
    Remove-Item -LiteralPath $Venv -Recurse -Force
}

if (-not (Test-Path $VenvPython)) {
    Write-Log 'Creating a clean private virtual environment under LocalAppData.'
    Remove-Item -LiteralPath $Venv -Recurse -Force -ErrorAction SilentlyContinue
    & $SystemPython.Exe -m venv $Venv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) {
        throw "Python virtual-environment creation failed using $($SystemPython.Exe)."
    }
}

if (-not (Test-Path $VenvPythonW)) {
    # Standard Windows venvs should contain pythonw.exe. If not, use python.exe;
    # the GUI still works, although the launcher console may remain attached.
    $VenvPythonW = $VenvPython
}

$env:PIP_CACHE_DIR = $PipCache
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$env:PIP_NO_INPUT = '1'
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONUTF8 = '1'

Write-Log 'Checking pip in the private virtual environment.'
& $VenvPython -m pip --version
if ($LASTEXITCODE -ne 0) {
    Write-Log 'pip is missing in the virtual environment; running ensurepip.'
    & $VenvPython -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) { throw 'Could not bootstrap pip in the private virtual environment.' }
}

$Requirements = if ($IncludeBuildTools) {
    Join-Path $PackageRoot 'requirements-dev.txt'
} else {
    Join-Path $PackageRoot 'requirements.txt'
}
if (-not (Test-Path $Requirements)) { throw "Requirements file not found: $Requirements" }

$ReqHash = (Get-FileHash -LiteralPath $Requirements -Algorithm SHA256).Hash
$MarkerName = if ($IncludeBuildTools) { '.requirements-dev.sha256' } else { '.requirements.sha256' }
$Marker = Join-Path $Venv $MarkerName
$InstalledHash = if (Test-Path $Marker) { (Get-Content -LiteralPath $Marker -Raw).Trim() } else { '' }

if ($ForceRepair -or $InstalledHash -ne $ReqHash) {
    Write-Log ("Installing pinned dependencies from {0}." -f (Split-Path -Leaf $Requirements))
    Write-Log 'Dependencies are installed only inside the short LocalAppData virtual environment.'
    & $VenvPython -m pip install --disable-pip-version-check --no-warn-script-location --prefer-binary --only-binary=:all: -r $Requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed. See $LogFile and the console output above."
    }
    Set-Content -LiteralPath $Marker -Value $ReqHash -Encoding ASCII
}

Write-Log 'Verifying required Python modules.'
$Verify = @'
import sys
from PyQt5 import QtCore, QtGui, QtWidgets, QtPrintSupport
import pdfplumber, pypdf, openpyxl, rapidfuzz, PIL, requests
print('dependency check OK')
print('python', sys.version)
print('Qt', QtCore.QT_VERSION_STR, 'PyQt', QtCore.PYQT_VERSION_STR)
'@
& $VenvPython -c $Verify
if ($LASTEXITCODE -ne 0) { throw 'Dependency verification failed.' }

Write-Log 'Running an off-screen application smoke test against the packaged 70-record seed database.'
$SmokeDir = Join-Path $LocalBase 'smoke104'
Remove-Item -LiteralPath $SmokeDir -Recurse -Force -ErrorAction SilentlyContinue
$OldQt = $env:QT_QPA_PLATFORM
$OldData = $env:THERA_CURATOR_DATA_DIR
$OldPythonPath = $env:PYTHONPATH
try {
    $env:QT_QPA_PLATFORM = 'offscreen'
    $env:THERA_CURATOR_DATA_DIR = $SmokeDir
    $env:PYTHONPATH = $PackageRoot
    Push-Location $PackageRoot
    $Smoke = @'
from thera_curator.qt_compat import QtWidgets, BINDING
from thera_curator.db import Database
from thera_curator.ui import MainWindow
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
db = Database()
count = db.count_records()
if count != 70:
    raise RuntimeError('seed database count is %s, expected 70' % count)
w = MainWindow(db)
w.show()
app.processEvents()
print('application smoke test OK; binding=' + BINDING + '; records=' + str(count))
w.close()
db.close()
'@
    & $VenvPython -c $Smoke
    if ($LASTEXITCODE -ne 0) { throw 'Application smoke test failed.' }
} finally {
    Pop-Location -ErrorAction SilentlyContinue
    if ($null -eq $OldQt) { Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue } else { $env:QT_QPA_PLATFORM = $OldQt }
    if ($null -eq $OldData) { Remove-Item Env:THERA_CURATOR_DATA_DIR -ErrorAction SilentlyContinue } else { $env:THERA_CURATOR_DATA_DIR = $OldData }
    if ($null -eq $OldPythonPath) { Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue } else { $env:PYTHONPATH = $OldPythonPath }
    Remove-Item -LiteralPath $SmokeDir -Recurse -Force -ErrorAction SilentlyContinue
}

$Tess = Join-Path $PackageRoot 'vendor\tesseract\tesseract.exe'
$PopA = Join-Path $PackageRoot 'vendor\poppler\Library\bin\pdftoppm.exe'
$PopB = Join-Path $PackageRoot 'vendor\poppler\bin\pdftoppm.exe'
if (-not (Test-Path $Tess)) { Write-Log 'NOTE: bundled Tesseract is absent; database/search/review features still work.' }
if (-not ((Test-Path $PopA) -or (Test-Path $PopB))) { Write-Log 'NOTE: bundled Poppler is absent; database/search/review features still work.' }

if (-not $NoLaunch) {
    $RunScript = Join-Path $PackageRoot 'scripts\run_windows.py'
    if (-not (Test-Path $RunScript)) { throw 'scripts\run_windows.py was not found.' }
    Write-Log 'Starting Thera-SAbDab WHO INN Curator.'
    $env:PYTHONPATH = $PackageRoot
    $proc = Start-Process -FilePath $VenvPythonW -ArgumentList ('"{0}"' -f $RunScript) -WorkingDirectory $PackageRoot -PassThru
    if (-not $proc) { throw 'Failed to start the application process.' }
    Start-Sleep -Milliseconds 1200
    if ($proc.HasExited -and $proc.ExitCode -ne 0) {
        if (Test-Path $CrashLog) {
            throw "Application exited immediately. Crash log: $CrashLog"
        }
        throw "Application exited immediately with code $($proc.ExitCode)."
    }
}

Write-Log 'Windows bootstrap completed successfully.'
Write-Host ''
Write-Host ('System Python: ' + $SystemPython.Exe)
Write-Host ('Private environment: ' + $Venv)
Write-Host ('Log: ' + $LogFile)
