param(
    [string] $RestoreUrl,
    [string] $SourceUrl,
    [string] $RestoreUrlEnv = "FRESHFIRST_RESTORE_DATABASE_URL",
    [string] $SourceUrlEnv = "FRESHFIRST_SOURCE_DATABASE_URL"
)

$ErrorActionPreference = "Stop"
$psql = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psql) {
    throw "PostgreSQL client psql is required."
}

# Keep this list explicit so a restore that silently omits a table cannot pass with two zero counts.
$tables = @(
    "auth_rate_limits", "auth_sessions", "basket_items", "cooking_history",
    "ingredient_aliases", "ingredients", "pantry_items", "recipe_ingredients",
    "recipes", "schema_migrations", "shopping_items", "store_settings",
    "substitution_rules", "users"
)

function Resolve-DatabaseUrl([string] $Value, [string] $EnvironmentName, [string] $Role) {
    if ($Value) { return $Value }
    $fromEnvironment = [Environment]::GetEnvironmentVariable($EnvironmentName)
    if (-not $fromEnvironment) {
        throw "$Role database URL is required. Set $EnvironmentName or pass the URL explicitly."
    }
    return $fromEnvironment
}

# The URL is never written to output. Prefer environment variables so it is not in command history.
$restoreConnection = Resolve-DatabaseUrl $RestoreUrl $RestoreUrlEnv "Restore"
$sourceConnection = $null
if ($SourceUrl -or [Environment]::GetEnvironmentVariable($SourceUrlEnv)) {
    $sourceConnection = Resolve-DatabaseUrl $SourceUrl $SourceUrlEnv "Source"
}

function Invoke-Query([string] $Url, [string] $Sql) {
    $result = & $psql.Source --dbname=$Url --tuples-only --no-align --quiet `
        --set=ON_ERROR_STOP=1 --command=$Sql
    if ($LASTEXITCODE -ne 0) { throw "Could not query the isolated PostgreSQL restore." }
    return ($result -join "").Trim()
}

$tableLiterals = ($tables | ForEach-Object { "'$_'" }) -join ","
$schemaQuery = @"
SELECT jsonb_build_object(
  'tables', COALESCE((SELECT jsonb_agg(table_name ORDER BY table_name)
    FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'), '[]'::jsonb),
  'columns', COALESCE((SELECT jsonb_agg(jsonb_build_object(
      'table', table_name, 'column', column_name, 'position', ordinal_position,
      'type', data_type, 'udt', udt_name, 'nullable', is_nullable,
      'default', COALESCE(column_default, '')
    ) ORDER BY table_name, ordinal_position)
    FROM information_schema.columns WHERE table_schema = 'public'
      AND table_name IN ($tableLiterals)), '[]'::jsonb),
  'foreign_keys', COALESCE((SELECT jsonb_agg(jsonb_build_object(
      'constraint', tc.constraint_name, 'table', tc.table_name, 'column', kcu.column_name,
      'references_table', ccu.table_name, 'references_column', ccu.column_name
    ) ORDER BY tc.table_name, tc.constraint_name, kcu.ordinal_position)
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON kcu.constraint_schema = tc.constraint_schema
     AND kcu.constraint_name = tc.constraint_name AND kcu.table_name = tc.table_name
    JOIN information_schema.constraint_column_usage ccu
      ON ccu.constraint_schema = tc.constraint_schema AND ccu.constraint_name = tc.constraint_name
    WHERE tc.constraint_schema = 'public' AND tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_name IN ($tableLiterals)), '[]'::jsonb)
)::text;
"@

$foreignKeyChecks = @(
    @{ Name = "pantry_items.owner_id -> users.id"; Sql = "SELECT count(*) FROM public.pantry_items p LEFT JOIN public.users u ON u.id = p.owner_id WHERE p.owner_id IS NOT NULL AND u.id IS NULL" },
    @{ Name = "pantry_items.ingredient_id -> ingredients.id"; Sql = "SELECT count(*) FROM public.pantry_items p LEFT JOIN public.ingredients i ON i.id = p.ingredient_id WHERE p.ingredient_id IS NOT NULL AND i.id IS NULL" },
    @{ Name = "recipe_ingredients.recipe_id -> recipes.id"; Sql = "SELECT count(*) FROM public.recipe_ingredients r LEFT JOIN public.recipes x ON x.id = r.recipe_id WHERE x.id IS NULL" },
    @{ Name = "recipe_ingredients.ingredient_id -> ingredients.id"; Sql = "SELECT count(*) FROM public.recipe_ingredients r LEFT JOIN public.ingredients i ON i.id = r.ingredient_id WHERE i.id IS NULL" },
    @{ Name = "substitution_rules.original_ingredient_id -> ingredients.id"; Sql = "SELECT count(*) FROM public.substitution_rules r LEFT JOIN public.ingredients i ON i.id = r.original_ingredient_id WHERE i.id IS NULL" },
    @{ Name = "substitution_rules.substitute_ingredient_id -> ingredients.id"; Sql = "SELECT count(*) FROM public.substitution_rules r LEFT JOIN public.ingredients i ON i.id = r.substitute_ingredient_id WHERE i.id IS NULL" },
    @{ Name = "basket_items.owner_id -> users.id"; Sql = "SELECT count(*) FROM public.basket_items b LEFT JOIN public.users u ON u.id = b.owner_id WHERE b.owner_id IS NOT NULL AND u.id IS NULL" },
    @{ Name = "basket_items.recipe_id -> recipes.id"; Sql = "SELECT count(*) FROM public.basket_items b LEFT JOIN public.recipes r ON r.id = b.recipe_id WHERE r.id IS NULL" },
    @{ Name = "shopping_items.owner_id -> users.id"; Sql = "SELECT count(*) FROM public.shopping_items s LEFT JOIN public.users u ON u.id = s.owner_id WHERE s.owner_id IS NOT NULL AND u.id IS NULL" },
    @{ Name = "shopping_items.ingredient_id -> ingredients.id"; Sql = "SELECT count(*) FROM public.shopping_items s LEFT JOIN public.ingredients i ON i.id = s.ingredient_id WHERE s.ingredient_id IS NOT NULL AND i.id IS NULL" },
    @{ Name = "cooking_history.owner_id -> users.id"; Sql = "SELECT count(*) FROM public.cooking_history h LEFT JOIN public.users u ON u.id = h.owner_id WHERE h.owner_id IS NOT NULL AND u.id IS NULL" },
    @{ Name = "cooking_history.recipe_id -> recipes.id"; Sql = "SELECT count(*) FROM public.cooking_history h LEFT JOIN public.recipes r ON r.id = h.recipe_id WHERE r.id IS NULL" },
    @{ Name = "store_settings.owner_id -> users.id"; Sql = "SELECT count(*) FROM public.store_settings s LEFT JOIN public.users u ON u.id = s.owner_id WHERE s.owner_id IS NOT NULL AND u.id IS NULL" },
    @{ Name = "auth_sessions.user_id -> users.id"; Sql = "SELECT count(*) FROM public.auth_sessions s LEFT JOIN public.users u ON u.id = s.user_id WHERE s.user_id IS NOT NULL AND u.id IS NULL" },
    @{ Name = "ingredient_aliases.ingredient_id -> ingredients.id"; Sql = "SELECT count(*) FROM public.ingredient_aliases a LEFT JOIN public.ingredients i ON i.id = a.ingredient_id WHERE i.id IS NULL" }
)

$invariantChecks = @(
    @{ Name = "pantry_items.nonnegative_quantity"; Sql = "SELECT count(*) FROM public.pantry_items WHERE (quantity_canonical IS NOT NULL AND quantity_canonical < 0) OR (quantity_entered IS NOT NULL AND quantity_entered < 0)" },
    @{ Name = "shopping_items.nonnegative_quantity"; Sql = "SELECT count(*) FROM public.shopping_items WHERE quantity_canonical < 0" },
    @{ Name = "shopping_items.transfer_requires_purchase"; Sql = "SELECT count(*) FROM public.shopping_items WHERE transferred_to_pantry AND NOT purchased" },
    @{ Name = "pantry_items.unresolved_has_no_ingredient"; Sql = "SELECT count(*) FROM public.pantry_items WHERE resolution_status = 'unresolved' AND ingredient_id IS NOT NULL" }
)

function Get-IntegritySnapshot([string] $Url) {
    $foreignKeys = [ordered]@{}
    foreach ($check in $foreignKeyChecks) { $foreignKeys[$check.Name] = [int64](Invoke-Query $Url $check.Sql) }
    $invariants = [ordered]@{}
    foreach ($check in $invariantChecks) { $invariants[$check.Name] = [int64](Invoke-Query $Url $check.Sql) }
    return [ordered]@{ foreign_keys = $foreignKeys; invariants = $invariants }
}

function Get-TableDigest([string] $Url, [string] $Table) {
    $key = if ($Table -eq "auth_sessions") { "token_hash" } elseif ($Table -eq "auth_rate_limits") { "bucket_hash" } elseif ($Table -eq "schema_migrations") { "version" } else { "id" }
    $quotedTable = '"' + $Table + '"'
    $quotedKey = '"' + $key + '"'
    $sql = "SELECT count(*)::text || '|' || md5(COALESCE(string_agg(md5(to_jsonb(t)::text), ',' ORDER BY t.$quotedKey), '')) FROM public.$quotedTable t;"
    return Invoke-Query $Url $sql
}

function Get-DatabaseSnapshot([string] $Url) {
    $schema = Invoke-Query $Url $schemaQuery
    $schemaObject = $schema | ConvertFrom-Json
    $missing = @($tables | Where-Object { $_ -notin @($schemaObject.tables) })
    if ($missing.Count -gt 0) { throw ("Required public tables are missing: {0}" -f ($missing -join ", ")) }
    $digests = [ordered]@{}
    foreach ($table in $tables) { $digests[$table] = Get-TableDigest $Url $table }
    return [ordered]@{
        schema = $schema
        tables = $digests
        integrity = Get-IntegritySnapshot $Url
    }
}

$restored = Get-DatabaseSnapshot $restoreConnection
Write-Output ("Restored schema/tables/integrity verified; table digests: {0}" -f ($restored.tables | ConvertTo-Json -Compress))

function Has-NonzeroValue($Map) { return (($Map.Values | Where-Object { $_ -ne 0 }).Count -gt 0) }
if (Has-NonzeroValue $restored.integrity.foreign_keys -or Has-NonzeroValue $restored.integrity.invariants) {
    throw "The isolated restore violates a FreshFirst relational invariant."
}

if ($sourceConnection) {
    $source = Get-DatabaseSnapshot $sourceConnection
    if ($source.schema -ne $restored.schema) { throw "Source and restored public schema snapshots differ." }
    if (($source.tables | ConvertTo-Json -Compress) -ne ($restored.tables | ConvertTo-Json -Compress)) {
        throw "Source and restored canonical table digests differ."
    }
    if (($source.integrity | ConvertTo-Json -Compress) -ne ($restored.integrity | ConvertTo-Json -Compress)) {
        throw "Source and restored relational integrity snapshots differ."
    }
    Write-Output "Source and isolated restore schema, canonical row digests, and relational integrity match."
}
