# Safe apply of loginTheme=stockpilot on an EXISTING Keycloak realm.
# Does NOT delete volumes or Postgres data.
# Locale array is applied via docker compose cp of a JSON file (never through PowerShell argv).
#
# Usage (dev stack already up):
#   powershell -File .\infra\keycloak\apply-login-theme.ps1
#
# Optional env:
#   KEYCLOAK_SERVICE=keycloak
#   KEYCLOAK_ADMIN=admin
#   KEYCLOAK_ADMIN_PASSWORD=admin
#   COMPOSE_PROJECT=stockpilot
#   COMPOSE_FILES  (space-separated -f args, optional; e.g. "compose.yaml compose.dev.yaml")

$ErrorActionPreference = "Stop"
$Service = if ($env:KEYCLOAK_SERVICE) { $env:KEYCLOAK_SERVICE } else { "keycloak" }
$Admin = if ($env:KEYCLOAK_ADMIN) { $env:KEYCLOAK_ADMIN } else { "admin" }
$Password = if ($env:KEYCLOAK_ADMIN_PASSWORD) { $env:KEYCLOAK_ADMIN_PASSWORD } else { "admin" }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocaleFile = Join-Path $ScriptDir "locales-fa-only.json"

$ComposeArgs = @()
if ($env:COMPOSE_PROJECT) {
  $ComposeArgs += @("-p", $env:COMPOSE_PROJECT)
}
if ($env:COMPOSE_FILES) {
  foreach ($f in ($env:COMPOSE_FILES -split "\s+")) {
    if ($f) { $ComposeArgs += @("-f", $f) }
  }
}

function Invoke-Compose {
  param([Parameter(Mandatory = $true)][string[]]$Args)
  Write-Host ("docker compose " + ($Args -join " "))
  & docker compose @ComposeArgs @Args
  if ($LASTEXITCODE -ne 0) {
    throw "command failed with exit code $LASTEXITCODE"
  }
}

if (-not (Test-Path $LocaleFile)) {
  throw "Missing $LocaleFile"
}

Write-Host "Configuring kcadm credentials against $Service ..."
Invoke-Compose @(
  "exec", "-T", $Service, "/opt/keycloak/bin/kcadm.sh",
  "config", "credentials",
  "--server", "http://localhost:8080",
  "--realm", "master",
  "--user", $Admin,
  "--password", $Password
)

Write-Host "Updating realms/stockpilot theme + defaultLocale ..."
Invoke-Compose @("exec", "-T", $Service, "/opt/keycloak/bin/kcadm.sh", "update", "realms/stockpilot", "-s", "loginTheme=stockpilot")
Invoke-Compose @("exec", "-T", $Service, "/opt/keycloak/bin/kcadm.sh", "update", "realms/stockpilot", "-s", "internationalizationEnabled=true")
Invoke-Compose @("exec", "-T", $Service, "/opt/keycloak/bin/kcadm.sh", "update", "realms/stockpilot", "-s", "defaultLocale=fa")

Write-Host "Copying Persian-only locales JSON into container ..."
Invoke-Compose @("cp", $LocaleFile, "${Service}:/tmp/sp-locales.json")

Write-Host "Applying supportedLocales=[fa] (English removed) ..."
Invoke-Compose @("exec", "-T", $Service, "/opt/keycloak/bin/kcadm.sh", "update", "realms/stockpilot", "-f", "/tmp/sp-locales.json")

Write-Host "Done. Open the Keycloak login page and hard-refresh (Ctrl+F5)."
