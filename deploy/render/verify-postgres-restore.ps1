param(
    [Parameter(Mandatory = $true)]
    [string] $RestoreUrl,
    [string] $SourceUrl
)

$ErrorActionPreference = "Stop"
$psql = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psql) {
    throw "PostgreSQL client psql is required."
}

$tables = @("users", "auth_sessions", "pantry_items", "recipes", "basket_items", "shopping_items", "cooking_history")
$query = ($tables | ForEach-Object { "'$_', (SELECT count(*) FROM public.$_)" }) -join ", "
$query = "SELECT json_build_object($query)::text;"

function Invoke-CountQuery([string] $Url) {
    $result = & $psql.Source --dbname=$Url --tuples-only --no-align --command=$query
    if ($LASTEXITCODE -ne 0) {
        throw "Could not query the isolated PostgreSQL restore."
    }
    return $result.Trim()
}

$restored = Invoke-CountQuery $RestoreUrl
Write-Output ("Restored database counts: {0}" -f $restored)
if ($SourceUrl) {
    $source = Invoke-CountQuery $SourceUrl
    if ($source -ne $restored) {
        throw "Source and restored entity counts differ."
    }
    Write-Output "Source and isolated restore counts match."
}
