# Run the elliptical-fiber queue one unit at a time, but never start a unit that is
# not expected to finish before -Deadline (so the machine is free by then).
# Estimates: max(default, 1.15 x longest unit of that solver seen in this run).
# Log: runs\run_until.log. Start it outside the IDE's process tree:
#
#   Invoke-CimMethod Win32_Process -MethodName Create -Arguments @{ CommandLine =
#       'powershell -NoProfile -ExecutionPolicy Bypass -File "<dir>\run_until.ps1" -Deadline 08:00'; CurrentDirectory = '<dir>' }
param([string]$Deadline = "08:00", [double]$AnsysHours = 2.0, [double]$FftHours = 4.0)

Set-Location $PSScriptRoot
$scenarios = "aspect_sweep_cf_epoxy", "fscatter_ab15_cf_epoxy", "fscatter_ab2_cf_epoxy", "fscatter_ab3_cf_epoxy",
             "aspect_dataset_cf_epoxy_n25", "fscatter_ab15_dataset_cf_epoxy_n25",
             "fscatter_ab2_dataset_cf_epoxy_n25", "fscatter_ab3_dataset_cf_epoxy_n25"
$log = "runs\run_until.log"
function Log($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" | Add-Content $log -Encoding utf8 }

$end = [datetime]::Today.Add([timespan]::Parse($Deadline))
if ($end -le (Get-Date)) { $end = $end.AddDays(1) }
$est = @{ ansys = $AnsysHours; fft = $FftHours }
$lastUnit = ""
Log "started, deadline $end, estimates ANSYS ${AnsysHours} h, FFT ${FftHours} h"

while ($true) {
    $next = (& python next_unit.py @scenarios | Select-Object -Last 1)
    if (-not $next) { Log "all units done"; break }
    $scen, $solver, $value = $next -split ' '
    if ($next -eq $lastUnit) { Log "unit '$next' did not finish (failed?) - stopping"; break }
    $eta = (Get-Date).AddHours($est[$solver])
    if ($eta -gt $end) { Log "next: $next, est. $($est[$solver]) h -> would end $eta, after deadline; stopping"; break }
    Log "start: $next (est. end $eta)"
    $t0 = Get-Date
    & (Join-Path $PSScriptRoot "run_detached.ps1") $scen --limit 1
    $h = ((Get-Date) - $t0).TotalHours
    Log ("done:  $next in {0:N2} h" -f $h)
    $est[$solver] = [Math]::Max($est[$solver], 1.15 * $h)
    $lastUnit = $next
}
Log "exit"
