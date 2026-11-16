# Run all elliptical-fiber scenarios (config.py, scenarios 9-16) one after another,
# each through run_detached.ps1 (log in runs\<scenario>\run.log). Finished units are
# skipped, so re-running resumes. Start it outside the IDE's process tree, so that
# closing PyCharm does not take it down:
#
#   Invoke-CimMethod Win32_Process -MethodName Create -Arguments @{ CommandLine =
#       'powershell -NoProfile -ExecutionPolicy Bypass -File "<dir>\run_ellipse.ps1"'; CurrentDirectory = '<dir>' }
Set-Location $PSScriptRoot
foreach ($s in "aspect_sweep_cf_epoxy",
               "fscatter_ab15_cf_epoxy",
               "fscatter_ab2_cf_epoxy",
               "fscatter_ab3_cf_epoxy",
               "aspect_dataset_cf_epoxy_n25",
               "fscatter_ab15_dataset_cf_epoxy_n25",
               "fscatter_ab2_dataset_cf_epoxy_n25",
               "fscatter_ab3_dataset_cf_epoxy_n25") {
    & (Join-Path $PSScriptRoot "run_detached.ps1") $s
}
