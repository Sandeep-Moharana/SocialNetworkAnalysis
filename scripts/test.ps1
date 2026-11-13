# Run the unit tests (tiny graphs with known answers) inside the spark-client container.
#   .\scripts\test.ps1
# Exit code 0 = all tests passed.
& (Join-Path $PSScriptRoot "submit.ps1") tests\run_tests.py
exit $LASTEXITCODE
