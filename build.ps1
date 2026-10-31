# build.ps1 - ???? Mini-DSO ?? (SDCC 4.x)
# ??: powershell -File build.ps1
$ErrorActionPreference = 'Continue'
$ws = Split-Path -Parent $MyInvocation.MyCommand.Path
$out = Join-Path $ws 'build\wusi_minidso.hex'
$obj = Join-Path $env:TEMP ('minidso_build_' + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Force (Join-Path $obj 'src'), (Join-Path $obj 'user') | Out-Null

# --stack-auto ????: 8051 ???? RAM ?? 128B, ???????
$flags = @('-mmcs51','--model-large','--opt-code-size','--std-c23','--stack-auto')
$inc   = Join-Path $ws 'include'
$fail  = 0

foreach ($cf in Get-ChildItem (Join-Path $ws 'src') -Filter *.c) {
    $o = Join-Path "$obj\src" ($cf.BaseName + '.rel')
    $r = & sdcc @flags '-I' $inc -c $cf.FullName -o $o 2>&1
    if ($LASTEXITCODE -ne 0) { $fail++; Write-Host "FAIL $($cf.Name)"; $r }
}
foreach ($cf in Get-ChildItem (Join-Path $ws 'user') -Filter *.c) {
    $o = Join-Path "$obj\user" ($cf.BaseName + '.rel')
    $r = & sdcc @flags '-I' $inc -c $cf.FullName -o $o 2>&1
    if ($LASTEXITCODE -ne 0) { $fail++; Write-Host "FAIL $($cf.Name)"; $r }
}
if ($fail -ne 0) { Write-Host "????: $fail ???"; exit 1 }

& sdar -rcs (Join-Path $obj 'minidso.lib') (Get-ChildItem "$obj\src" -Filter *.rel | ForEach-Object FullName)
& sdranlib (Join-Path $obj 'minidso.lib')
& sdcc @flags '--iram-size' '256' '--xram-size' '8192' '--code-size' '64512' '--out-fmt-ihx' `
      (Join-Path "$obj\user" 'main.rel') (Join-Path $obj 'minidso.lib') -o $out
if ($LASTEXITCODE -ne 0) { Write-Host "????"; exit 1 }

Copy-Item (Join-Path $obj 'wusi_minidso.mem') (Join-Path $ws 'build\wusi_minidso.mem') -Force
Get-Content (Join-Path $obj 'wusi_minidso.mem') | Select-String -Pattern 'ROM/EPROM|EXTERNAL RAM|Stack starts'
Write-Host ("??: {0} ({1} ??, {2} ???)" -f $out, (Get-Item $out).Length, (Get-Content $out).Count)
