param(
    [ValidateSet('bootstrap','prepare','prepare-tpch','build','micro','tpch','all','report','test','benchmark')]
    [string]$Action = 'all'
)
$taskScript = Join-Path $PSScriptRoot 'scripts/repro.sh'
$taskLinuxScript = (& wsl.exe -d Ubuntu-20.04 --exec wslpath -a $taskScript).Trim()
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& wsl.exe -d Ubuntu-20.04 --exec bash $taskLinuxScript $Action
exit $LASTEXITCODE
