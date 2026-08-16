$ErrorActionPreference = "Stop"
$ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
python "$ScriptDirectory\capacity.py" --config "$ScriptDirectory\stress-test.env" @args
