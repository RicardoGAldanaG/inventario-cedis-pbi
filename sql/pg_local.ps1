<#
  Servidor PostgreSQL local del proyecto (sin servicio de Windows ni permisos de administrador).

    .\sql\pg_local.ps1 crear     # una sola vez: crea el clúster en $Datos, puerto 5433, solo localhost
    .\sql\pg_local.ps1 iniciar
    .\sql\pg_local.ps1 detener
    .\sql\pg_local.ps1 estado

  El clúster usa autenticación "trust" restringida a 127.0.0.1 y ::1: sirve para un demo en la
  propia computadora, no para un servidor compartido.
#>
param([ValidateSet("crear", "iniciar", "detener", "estado")][string]$Accion = "estado",
      [string]$Bin = "C:\Program Files\PostgreSQL\12\bin",
      [string]$Datos = "$env:USERPROFILE\pgdata\inventario_cedis",
      [int]$Puerto = 5433)

$log = "$Datos.log"
switch ($Accion) {
  "crear" {
    if (Test-Path $Datos) { "Ya existe $Datos"; break }
    & "$Bin\initdb.exe" -D $Datos -U postgres --auth=trust --encoding=UTF8 --locale=C
    Add-Content "$Datos\postgresql.conf" "`nport = $Puerto`nlisten_addresses = 'localhost'"
  }
  "iniciar" {
    # Start-Process desacopla el servidor de la consola que lo lanza
    Start-Process -FilePath "$Bin\pg_ctl.exe" -ArgumentList "-D", "`"$Datos`"", "-l", "`"$log`"", "start" -WindowStyle Hidden
    for ($i = 0; $i -lt 20; $i++) {
      Start-Sleep -Milliseconds 500
      & "$Bin\pg_isready.exe" -h localhost -p $Puerto -U postgres | Out-Null
      if ($LASTEXITCODE -eq 0) { "PostgreSQL listo en localhost:$Puerto"; return }
    }
    "No respondió; revisa $log"
  }
  "detener" { & "$Bin\pg_ctl.exe" -D $Datos -m fast -w stop }
  "estado" { & "$Bin\pg_isready.exe" -h localhost -p $Puerto -U postgres }
}
