# Run one scenario as a process independent of the terminal/IDE that started it.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_detached.ps1 vf_dataset_cf_epoxy --report
#
# Output goes to runs\<scenario>\run.log; follow it with
#   Get-Content runs\<scenario>\run.log -Wait -Tail 20
# Re-running resumes: finished units are skipped.
param([Parameter(Mandatory = $true)][string]$Scenario, [Parameter(ValueFromRemainingArguments = $true)]$Rest)

# MatViz3D location: set MATVIZ3D_EXE / MATVIZ3D_DLL_DIRS in your environment, or
# replace the placeholders below with your paths (DLL dirs: Qt, MinGW, HDF5; ';'-separated).
if (-not $env:MATVIZ3D_EXE)      { $env:MATVIZ3D_EXE      = "<path-to>\MatViz3D.exe" }
if (-not $env:MATVIZ3D_DLL_DIRS) { $env:MATVIZ3D_DLL_DIRS = "<Qt>\Tools\mingw<ver>_64\bin;<Qt>\<ver>\mingw_64\bin;<HDF5>\bin" }
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
