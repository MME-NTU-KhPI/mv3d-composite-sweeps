# Run one scenario as a process independent of the terminal/IDE that started it.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_detached.ps1 vf_dataset_cf_epoxy --report
#
# Output goes to runs\<scenario>\run.log; follow it with
#   Get-Content runs\<scenario>\run.log -Wait -Tail 20
# Re-running resumes: finished units are skipped.
param([Parameter(Mandatory = $true)][string]$Scenario, [Parameter(ValueFromRemainingArguments = $true)]$Rest)

$env:MATVIZ3D_EXE      = "D:\MatViz3D-qml-main\build\Desktop_Qt_6_9_0_MinGW_64_bit-Release\release\MatViz3D.exe"
$env:MATVIZ3D_DLL_DIRS = "C:\Qt\Tools\mingw1310_64\bin;C:\Qt\6.9.0\mingw_64\bin;C:\Program Files\HDF_Group\HDF5\1.14.6\bin"
$env:QT_FORCE_STDERR_LOGGING = "1"   # MatViz3D --nogui otherwise sends its log to the debugger only
$env:PYTHONUNBUFFERED = "1"

Set-Location $PSScriptRoot
# Stop flag: if runs\STOP exists, do not start any new scenario (lets a queue end cleanly).
if (Test-Path (Join-Path $PSScriptRoot "runs\STOP")) { Write-Host "runs\STOP present, skipping $Scenario"; exit }
$rundir = Join-Path "runs" $Scenario
New-Item -ItemType Directory -Force $rundir | Out-Null
$log = Join-Path $rundir "run.log"
if (Test-Path $log) { Rename-Item $log ("run_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log") }

& python run.py $Scenario @Rest *> $log
