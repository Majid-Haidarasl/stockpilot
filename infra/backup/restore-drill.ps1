#Requires -Version 5.1
<#
.SYNOPSIS
  Repeatable StockPilot restore drill under -p stockpilot-restore only.

.DESCRIPTION
  Starts postgres, restores the latest (or RESTIC_SNAPSHOT) restic snapshot via
  compose profile backup, migrates, brings up the app plane, runs verifications,
  and prints wall-clock timings. Never down -v. Never deletes volumes.

.NOTES
  Run from anywhere; script cd's to the stockpilot repo root.
  Requires: Docker Compose, external volume stockpilot_restic_practice,
  env.restore (copied from env.restore.example if missing).
#>
[CmdletBinding()]
param(
    [string]$Snapshot = "",
    [switch]$SkipRepublish
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

$DockerBin = "C:\Users\majid\AppData\Local\Programs\DockerDesktop\resources\bin"
if (Test-Path $DockerBin) {
    $env:Path = "$DockerBin;$env:Path"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker not found on PATH"
}

$EnvFile = Join-Path $RepoRoot "env.restore"
$EnvExample = Join-Path $RepoRoot "env.restore.example"
if (-not (Test-Path $EnvFile)) {
    if (-not (Test-Path $EnvExample)) {
        throw "Missing env.restore and env.restore.example"
    }
    Copy-Item $EnvExample $EnvFile
    Write-Host "Created env.restore from env.restore.example (align RESTIC_PASSWORD with the source backup)."
}

$Confirm = (Select-String -Path $EnvFile -Pattern '^\s*STOCKPILOT_RESTORE_CONFIRM=(.+)$' |
    Select-Object -First 1).Matches.Groups[1].Value.Trim()
if ($Confirm -ne "stockpilot-restore") {
    throw "env.restore STOCKPILOT_RESTORE_CONFIRM must be exactly stockpilot-restore (got '$Confirm')"
}

$vol = docker volume inspect stockpilot_restic_practice 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "External volume stockpilot_restic_practice not found. Run a practice backup on the default stockpilot project first."
}

$ComposeArgs = @(
    "-f", "compose.yaml",
    "-f", "compose.restore.yaml",
    "-p", "stockpilot-restore",
    "--env-file", "env.restore"
)

function Invoke-Native {
    # Docker writes progress to stderr; with $ErrorActionPreference=Stop that becomes
    # a terminating NativeCommandError. Soften only around the native call.
    param([scriptblock]$Command)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        return & $Command
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Invoke-RestoreCompose {
    param([Parameter(Mandatory = $true)][string[]]$ComposeCommand)
    $out = Invoke-Native { & docker compose @ComposeArgs @ComposeCommand 2>&1 }
    foreach ($line in @($out)) { Write-Host $line }
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed (exit $LASTEXITCODE): docker compose $($ComposeCommand -join ' ')"
    }
}

function Invoke-Psql {
    param(
        [string]$Database = "stockpilot",
        [string]$User = "postgres",
        [string]$Sql,
        [string]$Password = "",
        [switch]$PassThru
    )
    $envArgs = @()
    if ($Password) {
        $envArgs = @("-e", "PGPASSWORD=$Password")
    }
    $out = Invoke-Native {
        $Sql | & docker compose @ComposeArgs exec -T @envArgs postgres `
            psql -U $User -d $Database -v ON_ERROR_STOP=1 2>&1
    }
    foreach ($line in @($out)) { Write-Host $line }
    if ($LASTEXITCODE -ne 0) {
        throw "psql failed (exit $LASTEXITCODE) as $User on $Database"
    }
    if ($PassThru) {
        return ($out | Out-String)
    }
}

function Measure-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )
    Write-Host ""
    Write-Host "=== $Name ==="
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $null = & $Action
    $sw.Stop()
    $seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1)
    Write-Host "=== $Name done in ${seconds}s ==="
    return ,$seconds
}

Write-Host "StockPilot restore drill (project=stockpilot-restore)"
Write-Host "Repo: $RepoRoot"

if ($Snapshot) {
    $env:RESTIC_SNAPSHOT = $Snapshot
    Write-Host "RESTIC_SNAPSHOT override: $Snapshot"
}

$tPostgres = Measure-Step "postgres up --wait" {
    Invoke-RestoreCompose -ComposeCommand @("up", "-d", "--wait", "postgres")
}

$tRoles = Measure-Step "ensure-db-roles" {
    Invoke-RestoreCompose -ComposeCommand @(
        "run", "--rm", "ops",
        "python", "-m", "stockpilot.bootstrap.ops", "ensure-db-roles"
    )
}

$script:RestoredSnapshotId = $null
$tRestore = Measure-Step "restic restore + pg_restore + media" {
    Invoke-RestoreCompose -ComposeCommand @("--profile", "backup", "build", "restore")
    $restoreOut = Invoke-Native {
        & docker compose @ComposeArgs --profile backup run --rm restore 2>&1
    }
    foreach ($line in @($restoreOut)) {
        Write-Host $line
        $text = $line.ToString()
        if ($text -match 'restoring snapshot ([a-f0-9]+)') {
            $script:RestoredSnapshotId = $Matches[1]
        }
    }
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose restore failed (exit $LASTEXITCODE)"
    }
}

$tMigrate = Measure-Step "migrate" {
    Invoke-RestoreCompose -ComposeCommand @("run", "--rm", "migrate")
}

$tApp = Measure-Step "app plane up --wait" {
    Invoke-RestoreCompose -ComposeCommand @(
        "up", "-d", "--wait",
        "rabbitmq", "keycloak", "api", "relay", "worker", "scheduler"
    )
}

Write-Host ""
Write-Host "=== verifications ==="

function Get-PsqlScalar([string]$Sql) {
    $raw = Invoke-Native {
        & docker compose @ComposeArgs exec -T postgres `
            psql -U postgres -d stockpilot -Atqc $Sql 2>&1
    }
    if ($LASTEXITCODE -ne 0) {
        throw "psql scalar failed: $Sql`n$raw"
    }
    return (@($raw) | Select-Object -Last 1).ToString().Trim()
}

Write-Host "-- alembic + function owners --"
$ownersOut = Invoke-Psql -PassThru -Sql @"
SELECT version_num FROM alembic_version;
SELECT p.proname, r.rolname AS owner
FROM pg_proc p
JOIN pg_roles r ON r.oid = p.proowner
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'platform'
  AND p.proname IN ('record_backup_heartbeat', 'outbox_lag', 'failed_jobs_metrics')
ORDER BY 1;
"@
if ($ownersOut -notmatch "0015_backup_heartbeat") {
    throw "expected alembic 0015_backup_heartbeat"
}
if ($ownersOut -notmatch "record_backup_heartbeat\s+\|\s+stockpilot_migrator") {
    throw "record_backup_heartbeat owner must be stockpilot_migrator"
}

Write-Host "-- FORCE RLS on tenant tables --"
$forceOut = Invoke-Psql -PassThru -Sql @"
SELECT c.relname, c.relforcerowsecurity
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname IN ('sales', 'catalog', 'access')
  AND c.relkind = 'r'
  AND c.relname IN ('products', 'product_images', 'orders', 'order_lines', 'customers', 'memberships', 'tenants')
ORDER BY 1;
"@
if ($forceOut -notmatch "products") {
    throw "FORCE RLS query returned no tenant tables"
}
if ($forceOut -match '\| f\b' -or $forceOut -match '\| false\b') {
    throw "FORCE RLS missing on one or more tenant tables"
}

Write-Host "-- product count --"
$productCount = Get-PsqlScalar "SELECT COUNT(*) FROM catalog.products;"
Write-Host "product_count=$productCount"
if (-not ($productCount -as [int]) -or [int]$productCount -le 0) {
    throw "expected product_count > 0, got '$productCount'"
}

Write-Host "-- sample image file --"
$storageKey = Get-PsqlScalar "SELECT storage_key FROM catalog.product_images LIMIT 1;"
if (-not $storageKey) {
    throw "no product_images.storage_key found"
}
$imageCheck = Invoke-Native {
    & docker compose @ComposeArgs exec -T api sh -c "test -f /var/lib/stockpilot/media/$storageKey && echo IMAGE_OK || echo IMAGE_MISSING"
}
$imageCheck = ($imageCheck | Select-Object -Last 1).ToString().Trim()
Write-Host "storage_key=$storageKey -> $imageCheck"
if ($imageCheck -ne "IMAGE_OK") {
    throw "sampled media file missing: $storageKey"
}

Write-Host "-- grants (backup EXECUTE + heartbeats) --"
Invoke-Psql -Sql @"
SELECT has_function_privilege(
  'stockpilot_backup',
  'platform.record_backup_heartbeat(jsonb)',
  'EXECUTE'
) AS backup_exec;
SELECT grantee, privilege_type
FROM information_schema.role_table_grants
WHERE table_schema = 'platform'
  AND table_name = 'heartbeats'
  AND grantee LIKE 'stockpilot_%'
ORDER BY 1, 2;
"@

Write-Host "-- RLS smoke (stockpilot_app + fake tenant) --"
$appPassword = (Select-String -Path $EnvFile -Pattern '^\s*STOCKPILOT_APP_PASSWORD=(.+)$' |
    Select-Object -First 1).Matches.Groups[1].Value.Trim()
if (-not $appPassword) { $appPassword = "app_dev_change_me" }
$rlsOut = Invoke-Native {
    @"
SELECT set_config('app.tenant_id', '00000000-0000-0000-0000-000000000001', false);
SELECT COUNT(*) AS visible_products FROM catalog.products;
"@ | & docker compose @ComposeArgs exec -T -e "PGPASSWORD=$appPassword" postgres `
        psql -U stockpilot_app -d stockpilot -v ON_ERROR_STOP=1 -At 2>&1
}
if ($LASTEXITCODE -ne 0) { throw "RLS smoke query failed" }
$visible = ($rlsOut | Select-Object -Last 1).ToString().Trim()
Write-Host "visible_products_fake_tenant=$visible"
if ($visible -ne "0") {
    throw "RLS smoke expected 0 visible products for fake tenant, got '$visible'"
}

Write-Host "-- API health + /auth/login 302 --"
$health = Invoke-Native {
    & docker compose @ComposeArgs exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/live').read().decode())"
}
Write-Host ($health | Out-String).Trim()
$login = Invoke-Native {
    & docker compose @ComposeArgs exec -T api python -c @"
import http.client
c = http.client.HTTPConnection('127.0.0.1', 8000)
c.request('GET', '/auth/login')
r = c.getresponse()
print(r.status)
print(r.getheader('Location') or '')
"@
}
$loginLines = @($login | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ })
$loginStatus = $loginLines[0]
$loginLoc = if ($loginLines.Count -gt 1) { $loginLines[1] } else { "" }
Write-Host "auth/login status=$loginStatus location=$loginLoc"
if ($loginStatus -ne "302") {
    throw "expected /auth/login 302, got $loginStatus"
}
if ($loginLoc -notmatch "openid-connect|/realms/|keycloak|auth") {
    throw "login Location does not look like Keycloak OIDC: $loginLoc"
}

Write-Host "-- published-without-Inbox count --"
$gapSql = "SELECT COUNT(*) FROM platform.outbox o WHERE o.published_at IS NOT NULL AND NOT EXISTS (SELECT 1 FROM platform.inbox i WHERE i.event_id = o.event_id);"
$gapBefore = Get-PsqlScalar $gapSql
Write-Host "published_without_inbox_before=$gapBefore"

if (-not $SkipRepublish -and [int]$gapBefore -gt 0) {
    Write-Host "-- controlled republish (restore project only; clear published_at) --"
    Invoke-Psql -Sql @"
UPDATE platform.outbox o
SET published_at = NULL,
    lease_owner = NULL,
    lease_expires_at = NULL
WHERE o.published_at IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM platform.inbox i WHERE i.event_id = o.event_id);
"@
    Start-Sleep -Seconds 8
    $gapAfter = Get-PsqlScalar $gapSql
    Write-Host "published_without_inbox_after=$gapAfter"
} else {
    $gapAfter = $gapBefore
}

$rto = [math]::Round($tRestore + $tMigrate + $tApp, 1)
$snapId = $script:RestoredSnapshotId

Write-Host ""
Write-Host "======== RESTORE DRILL SUMMARY ========"
Write-Host ("restic_snapshot_id={0}" -f $(if ($snapId) { $snapId } else { "(unknown)" }))
Write-Host ("postgres_up_s={0}" -f $tPostgres)
Write-Host ("ensure_db_roles_s={0}" -f $tRoles)
Write-Host ("restore_s={0}" -f $tRestore)
Write-Host ("migrate_s={0}" -f $tMigrate)
Write-Host ("app_plane_s={0}" -f $tApp)
Write-Host ("rto_post_postgres_s={0}" -f $rto)
Write-Host ("product_count={0}" -f $productCount)
Write-Host ("image={0}" -f $imageCheck)
Write-Host ("rls_visible_fake_tenant={0}" -f $visible)
Write-Host ("auth_login_status={0}" -f $loginStatus)
Write-Host ("published_without_inbox_before={0}" -f $gapBefore)
Write-Host ("published_without_inbox_after={0}" -f $gapAfter)
Write-Host "Teardown when done: docker compose -p stockpilot-restore stop   # NEVER down -v"
Write-Host "======== PASS ========"
