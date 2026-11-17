param([Parameter(Mandatory=$true)][string]$ExpectedFile)
$ErrorActionPreference = 'Stop'
$expectedCode = [System.IO.File]::ReadAllText($ExpectedFile)
$actualCode = Get-Clipboard -Raw
[pscustomobject]@{
    matchesExpected = ([string]$actualCode).Replace("`r`n", "`n") -ceq $expectedCode.Replace("`r`n", "`n")
} | ConvertTo-Json -Compress
