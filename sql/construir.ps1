<#
  Crea el esquema, carga los CSV, reconstruye y corre las pruebas en PostgreSQL.
  Correr desde cualquier carpeta: se ubica en la raíz del repo para las rutas de \copy.

    .\sql\construir.ps1                       # localhost:5433, base inventario_cedis
    .\sql\construir.ps1 -Puerto 5432 -Usuario postgres
#>
param([string]$Bin = "C:\Program Files\PostgreSQL\12\bin",
      [string]$Servidor = "localhost", [int]$Puerto = 5433,
      [string]$Usuario = "postgres", [string]$Base = "inventario_cedis")

$raiz = Split-Path $PSScriptRoot -Parent
Push-Location $raiz
try {
    foreach ($f in "01_esquema.sql", "02_carga.sql", "03_reconstruccion.sql", "04_vistas_pbi.sql", "05_pruebas.sql") {
        Write-Host "== $f"
        & "$Bin\psql.exe" -h $Servidor -p $Puerto -U $Usuario -d $Base -v ON_ERROR_STOP=1 -q -X -f "sql\$f"
        if ($LASTEXITCODE -ne 0) { throw "Falló $f" }
    }
} finally { Pop-Location }
