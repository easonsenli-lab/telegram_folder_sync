param(
    [string]$ProjectRoot = "E:\telegram_workspace\telegram_folder_sync",
    [string]$BackupRoot = "E:\telegram_workspace\telegram_folder_sync_code_backups"
)

$ErrorActionPreference = "Stop"

$project = Resolve-Path -LiteralPath $ProjectRoot
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
$backupDir = Resolve-Path -LiteralPath $BackupRoot

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$zipName = "telegram_folder_sync_code_$timestamp.zip"
$zipPath = Join-Path $backupDir $zipName
$stageRoot = Join-Path $env:TEMP "telegram_folder_sync_code_backup_$timestamp"

$excludedDirs = @(
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "dist",
    "build",
    "data",
    "accounts",
    "sessions",
    "state",
    "logs",
    "scratch"
)

$excludedFiles = @(
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.session",
    "*.session-journal",
    "*.zip",
    "*.tar",
    "*.tar.gz",
    ".env",
    ".env.*"
)

if (Test-Path -LiteralPath $stageRoot) {
    Remove-Item -LiteralPath $stageRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null

$robocopyArgs = @(
    $project.Path,
    $stageRoot,
    "/E",
    "/XD"
) + $excludedDirs + @(
    "/XF"
) + $excludedFiles + @(
    "/R:1",
    "/W:1",
    "/NFL",
    "/NDL",
    "/NP"
)

& robocopy @robocopyArgs | Out-Null
$robocopyExit = $LASTEXITCODE
if ($robocopyExit -ge 8) {
    throw "Robocopy failed with exit code $robocopyExit"
}

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -Path (Join-Path $stageRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal
Remove-Item -LiteralPath $stageRoot -Recurse -Force

$zipItem = Get-Item -LiteralPath $zipPath
Write-Output "Created backup: $($zipItem.FullName)"
Write-Output "Size: $([math]::Round($zipItem.Length / 1MB, 2)) MB"
