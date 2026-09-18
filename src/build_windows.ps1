param(
    [switch]$SkipTests,
    [switch]$RequireBundledOCR
)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$PackageRoot=$PSScriptRoot
Set-Location $PackageRoot

if($env:LOCALAPPDATA){ $Base=Join-Path $env:LOCALAPPDATA 'TSCurator' } else { $Base=Join-Path $env:TEMP 'TSCurator' }
$Python=Join-Path $Base 'venv104\Scripts\python.exe'
$Stage=Join-Path $Base 'buildsrc104'
$StageDist=Join-Path $Stage 'dist'

Write-Host 'Thera-SAbDab WHO INN Curator - Windows standalone build v1.0.4'
Write-Host 'This build uses the installed system Python only to create an isolated short-path build environment.'
Write-Host ''

$Bootstrap=Join-Path $PackageRoot 'scripts\windows_system_python_setup.ps1'
& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $Bootstrap -IncludeBuildTools -NoLaunch
if($LASTEXITCODE -ne 0){ throw 'Private Windows build environment setup failed.' }
if(-not (Test-Path $Python)){ throw "Private Python environment is missing: $Python" }

Write-Host ('Staging source under short path: ' + $Stage)
Remove-Item -LiteralPath $Stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

$Robo=Get-Command robocopy.exe -ErrorAction SilentlyContinue
if($Robo){
    & $Robo.Source $PackageRoot $Stage /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XD build dist .git logs __pycache__ /XF *.pyc *.pyo
    $RoboCode=$LASTEXITCODE
    if($RoboCode -ge 8){ throw "robocopy staging failed with exit code $RoboCode" }
}else{
    Get-ChildItem -LiteralPath $PackageRoot -Force | Where-Object { $_.Name -notin @('build','dist','.git','logs','__pycache__') } | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $Stage -Recurse -Force
    }
}

Set-Location $Stage
$tess = Test-Path '.\vendor\tesseract\tesseract.exe'
$pop = (Test-Path '.\vendor\poppler\Library\bin\pdftoppm.exe') -or (Test-Path '.\vendor\poppler\bin\pdftoppm.exe')
if($RequireBundledOCR -and (-not ($tess -and $pop))){ throw 'RequireBundledOCR requested, but bundled OCR tools are missing.' }
if(-not ($tess -and $pop)){ Write-Warning 'OCR tools are not bundled. Core application features still build and run.' }

if(-not $SkipTests){
    $env:QT_QPA_PLATFORM='offscreen'
    $env:PYTHONPATH=$Stage
    & $Python -m pytest -q
    if($LASTEXITCODE -ne 0){ throw 'Tests failed; packaging aborted.' }
}

Remove-Item -Recurse -Force build,dist -ErrorAction SilentlyContinue
& $Python -m PyInstaller --clean --noconfirm thera_curator.spec
if($LASTEXITCODE -ne 0){ throw 'PyInstaller failed.' }

$Bundle=Join-Path $StageDist 'Thera-SAbDab_WHO_INN_Curator'
if($tess -and $pop){
    & $Python scripts\verify_windows_bundle.py $Bundle
}else{
    & $Python scripts\verify_windows_bundle.py $Bundle --allow-external-ocr
}
if($LASTEXITCODE -ne 0){ throw 'Bundle verification failed.' }

$Version=((Get-Content VERSION -ErrorAction SilentlyContinue) -join '').Trim()
$Readme=@"
Thera-SAbDab WHO INN Curator $Version

Run Thera-SAbDab_WHO_INN_Curator.exe.
The writable database is created under LocalAppData on first launch.
"@
Set-Content -Path (Join-Path $Bundle 'README_FIRST.txt') -Value $Readme -Encoding UTF8

$StageZip=Join-Path $StageDist 'Thera-SAbDab_WHO_INN_Curator_Windows.zip'
Compress-Archive -Path (Join-Path $Bundle '*') -DestinationPath $StageZip -Force

$OutDist=Join-Path $PackageRoot 'dist'
Remove-Item -LiteralPath $OutDist -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $OutDist | Out-Null
Copy-Item -LiteralPath $Bundle -Destination $OutDist -Recurse -Force
Copy-Item -LiteralPath $StageZip -Destination (Join-Path $OutDist 'Thera-SAbDab_WHO_INN_Curator_Windows.zip') -Force

Write-Host ''
Write-Host 'Build complete:'
Write-Host ('  EXE: ' + (Join-Path $OutDist 'Thera-SAbDab_WHO_INN_Curator\Thera-SAbDab_WHO_INN_Curator.exe'))
Write-Host ('  ZIP: ' + (Join-Path $OutDist 'Thera-SAbDab_WHO_INN_Curator_Windows.zip'))
