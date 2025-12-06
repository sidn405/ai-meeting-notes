
# Database Migration Script
# Save as: run-migration.ps1

# Configuration
$DB_USER = "postgres"  # Change this
$DB_NAME = "railway"  # Change this
$DB_HOST = "postgres.railway.internal"
$DB_PORT = "5432"
$SQL_FILE = "database_migration.sql"

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Database Migration Script" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check if SQL file exists
if (-Not (Test-Path $SQL_FILE)) {
    Write-Host "❌ Error: $SQL_FILE not found!" -ForegroundColor Red
    Write-Host "Make sure you're in the outputs directory." -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Found SQL file: $SQL_FILE" -ForegroundColor Green

# Check if psql is available
try {
    $null = psql --version
    Write-Host "✅ PostgreSQL psql found" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: psql command not found!" -ForegroundColor Red
    Write-Host "Add PostgreSQL to your PATH or install PostgreSQL client." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Database Configuration:" -ForegroundColor Yellow
Write-Host "  Host: $DB_HOST" -ForegroundColor Gray
Write-Host "  Port: $DB_PORT" -ForegroundColor Gray
Write-Host "  Database: $DB_NAME" -ForegroundColor Gray
Write-Host "  User: $DB_USER" -ForegroundColor Gray
Write-Host ""

# Confirm
$confirm = Read-Host "Continue with migration? (y/n)"
if ($confirm -ne "y") {
    Write-Host "Migration cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Running migration..." -ForegroundColor Cyan

# Run migration
try {
    psql -U $DB_USER -d $DB_NAME -h $DB_HOST -p $DB_PORT -f $SQL_FILE
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "================================" -ForegroundColor Green
        Write-Host "✅ Migration completed successfully!" -ForegroundColor Green
        Write-Host "================================" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "❌ Migration failed with exit code: $LASTEXITCODE" -ForegroundColor Red
    }
} catch {
    Write-Host ""
    Write-Host "❌ Error running migration: $_" -ForegroundColor Red
    exit 1
}