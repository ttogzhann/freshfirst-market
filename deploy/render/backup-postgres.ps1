param(
    [Parameter()]
    [string] $OutputDirectory = "./render-backups"
)

$ErrorActionPreference = "Stop"

function Fail([string] $Message) {
    throw $Message
}

if (-not $env:RENDER_POSTGRES_EXTERNAL_URL) {
    Fail "Set RENDER_POSTGRES_EXTERNAL_URL in the current process environment. The value is never printed or written to disk."
}

$pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
$pgRestore = Get-Command pg_restore -ErrorAction SilentlyContinue
if (-not $pgDump -or -not $pgRestore) {
    Fail "PostgreSQL client tools pg_dump and pg_restore are required."
}

$url = $env:RENDER_POSTGRES_EXTERNAL_URL
if ($url -match "^postgresql\+[^:]+://") {
    $url = $url -replace "^postgresql\+[^:]+://", "postgresql://"
}
try {
    $connection = [Uri] $url
} catch {
    Fail "RENDER_POSTGRES_EXTERNAL_URL is not a valid PostgreSQL connection URL."
}
if ($connection.Scheme -ne "postgresql" -and $connection.Scheme -ne "postgres") {
    Fail "RENDER_POSTGRES_EXTERNAL_URL must use the postgresql:// scheme."
}
if (-not $connection.UserInfo) {
    Fail "RENDER_POSTGRES_EXTERNAL_URL must include a database user and password."
}

$userInfo = $connection.UserInfo.Split(":", 2)
if ($userInfo.Count -ne 2) {
    Fail "RENDER_POSTGRES_EXTERNAL_URL must include a database user and password."
}
$database = $connection.AbsolutePath.TrimStart("/")
if (-not $database) {
    Fail "RENDER_POSTGRES_EXTERNAL_URL must include a database name."
}

$output = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $output | Out-Null

if ($IsWindows -or $env:OS -eq "Windows_NT") {
    $acl = Get-Acl -LiteralPath $output
    $acl.SetAccessRuleProtection($true, $false)
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $rule = New-Object Security.AccessControl.FileSystemAccessRule($identity, "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
    $acl.SetAccessRule($rule)
    Set-Acl -LiteralPath $output -AclObject $acl
}

$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$dumpPath = Join-Path $output "freshfirst-$stamp.dump"
$checksumPath = "$dumpPath.sha256"
if ((Test-Path -LiteralPath $dumpPath) -or (Test-Path -LiteralPath $checksumPath)) {
    Fail "Refusing to overwrite an existing backup."
}

$previous = @{}
foreach ($name in @("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGSSLMODE")) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}
try {
    $env:PGHOST = $connection.Host
    $env:PGPORT = if ($connection.Port -gt 0) { $connection.Port } else { 5432 }
    $env:PGUSER = [Uri]::UnescapeDataString($userInfo[0])
    $env:PGPASSWORD = [Uri]::UnescapeDataString($userInfo[1])
    $env:PGDATABASE = [Uri]::UnescapeDataString($database)
    $env:PGSSLMODE = if ($env:RENDER_POSTGRES_SSLMODE) { $env:RENDER_POSTGRES_SSLMODE } else { "require" }

    & $pgDump.Source --host=$env:PGHOST --port=$env:PGPORT --username=$env:PGUSER --dbname=$env:PGDATABASE --format=custom --file=$dumpPath --schema=public --no-owner --no-privileges --no-comments --verbose 2>$null
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -LiteralPath $dumpPath -Force -ErrorAction SilentlyContinue
        Fail "pg_dump failed. No backup was retained."
    }

    & $pgRestore.Source --list $dumpPath *> $null
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -LiteralPath $dumpPath -Force -ErrorAction SilentlyContinue
        Fail "The generated backup failed pg_restore validation. No backup was retained."
    }

    $hash = (Get-FileHash -LiteralPath $dumpPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath $checksumPath -Value "$hash  $(Split-Path -Leaf $dumpPath)" -NoNewline -Encoding ascii
    Write-Output ("Backup created and validated: {0}" -f $dumpPath)
    Write-Output ("SHA-256 checksum: {0}" -f $checksumPath)
} finally {
    foreach ($name in $previous.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], "Process")
    }
}
