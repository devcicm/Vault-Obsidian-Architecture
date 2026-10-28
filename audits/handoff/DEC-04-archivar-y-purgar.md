# DEC-04 — archivar y purgar `vault-backups/` (runbook del propietario)

Decisión ratificada el 2026-10-28 (acta: [ACTA-DECISIONES-PROPIETARIO-2026-10-28.md](ACTA-DECISIONES-PROPIETARIO-2026-10-28.md#dec-04)).
El residuo solo existe en la máquina del propietario, así que lo ejecuta él.
Copia el bloque en un fichero `.ps1` **fuera del repo** y lánzalo desde la raíz del clon.
Se guarda como Markdown porque un `.ps1` dentro del árbol sería una frontera de lenguaje no declarada (AP-57, `vault_criterios`).

```powershell
<#
  DEC-04 (ratificada 2026-10-28): archivar vault-backups/ con verificación de
  hashes y después purgarlo. Lo ejecuta el PROPIETARIO en su máquina: el
  residuo solo existe ahí. Ni la CI ni las sesiones remotas lo ven.

  Uso, desde la raíz del clon:
    & $env:TEMP\dec04.ps1           # inventario + ZIP + verificación
    & $env:TEMP\dec04.ps1 -Purgar   # además, purga si todo coincide

  Ubicación del residuo: dos niveles por encima de vault-sandbox/, es decir,
  junto al clon (..\vault-backups). Esperado: 66 ficheros, 854.108 bytes.
  El ZIP y su inventario se quedan junto al clon y no entran en el repo.
#>
param([switch]$Purgar)
$ErrorActionPreference = "Stop"
$repo = (git rev-parse --show-toplevel).Trim()
$residuo = Join-Path (Split-Path $repo -Parent) "vault-backups"
$zip = Join-Path (Split-Path $repo -Parent) "vault-backups-2026-06-archivo.zip"
$inv = "$zip.sha256.txt"

if (-not (Test-Path $residuo)) { Write-Host "No existe $residuo : nada que archivar (ya purgado)."; exit 0 }

function Inventario($raiz) {
  Get-ChildItem -LiteralPath $raiz -Recurse -File -Force | Sort-Object FullName | ForEach-Object {
    $rel = $_.FullName.Substring($raiz.Length + 1).Replace('\', '/')
    "{0}  {1}  {2}" -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Length, $rel
  }
}

$antes = @(Inventario $residuo)
$bytes = ($antes | ForEach-Object { [long]($_ -split '  ')[1] } | Measure-Object -Sum).Sum
Write-Host "Inventario: $($antes.Count) ficheros, $bytes bytes (esperado: 66 / 854108)"
if ($antes.Count -ne 66 -or $bytes -ne 854108) {
  Write-Host "AVISO: no coincide con el apéndice A de QG-02-ESCENARIOS-Y-VAULT-BACKUPS.md. Se archiva igual, pero NO se purga." -ForegroundColor Yellow
  $Purgar = $false
}
$antes | Set-Content -LiteralPath $inv -Encoding UTF8

if (Test-Path $zip) { Remove-Item -LiteralPath $zip }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($residuo, $zip)

# Verificación: se extrae el ZIP aparte y se compara fichero a fichero.
$tmp = Join-Path $env:TEMP ("dec04-verif-" + [guid]::NewGuid())
[IO.Compression.ZipFile]::ExtractToDirectory($zip, $tmp)
$despues = @(Inventario $tmp)
Remove-Item -LiteralPath $tmp -Recurse -Force
$dif = Compare-Object $antes $despues
if ($dif) { $dif | Out-Host; throw "El ZIP NO reproduce el inventario. No se purga nada." }
$zipHash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLower()
Write-Host "ZIP verificado: $zip"
Write-Host "  sha256 del ZIP: $zipHash"
Write-Host "  inventario:     $inv"

if ($Purgar) {
  Remove-Item -LiteralPath $residuo -Recurse -Force
  Write-Host "Purgado: $residuo" -ForegroundColor Green
  Write-Host "Registra en DECISIONES-PROPIETARIO.md (DEC-04): fecha, sha256 del ZIP ($zipHash) y dónde lo guardas."
} else {
  Write-Host "No se purgó (falta -Purgar o el inventario no coincide)."
}
```
