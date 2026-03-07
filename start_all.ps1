<#
.SYNOPSIS
    Starts the entire Chatters application stack.

.DESCRIPTION
    Launches Docker containers (Kafka, Redis, Flink) and all Python services
    in separate terminal windows. Run from the chatters/ directory.

    Services started:
      [Docker]  Kafka (9092), Kafka UI (8080), Redis (6379)
      [Python]  Ingestion / Webhook server       (port 8000)
      [Python]  Masking service                   (Kafka consumer)
      [Python]  Clustering consumer               (Kafka consumer)
      [Python]  Summarization + API               (port 8570)
      [Python]  Categorize Model (Flask)          (port 8562)
      [Node]    Frontend (Vite dev server)        (port 5173)

.NOTES
    Press Ctrl+C in this window to stop everything (Docker containers + processes).
#>

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot                        # chatters/

# ──────────────────────────────────────────
# 1. Docker infrastructure
# ──────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Starting Docker infrastructure..." -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Kafka + Kafka UI
Write-Host "[Docker] Kafka + Kafka UI..." -ForegroundColor Yellow
docker compose -f "$ROOT\kafka\compose.yml" up -d

# Redis (masking/docker-compose.yml)
Write-Host "[Docker] Redis..." -ForegroundColor Yellow
docker compose -f "$ROOT\masking\docker-compose.yml" up -d

# Wait for Kafka to be healthy
Write-Host "`nWaiting for Kafka to be ready..." -ForegroundColor Yellow
$retries = 0
while ($retries -lt 30) {
    try {
        $result = docker exec kafka-1 /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Kafka is ready." -ForegroundColor Green
            break
        }
    } catch {}
    $retries++
    Start-Sleep -Seconds 2
}
if ($retries -ge 30) {
    Write-Host "[WARN] Kafka may not be fully ready yet. Continuing..." -ForegroundColor Red
}

# Ensure Kafka topics exist
Write-Host "Creating Kafka topics (if needed)..." -ForegroundColor Yellow
docker exec kafka-1 /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic raw-chat-stream --partitions 3 --replication-factor 1
docker exec kafka-1 /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic sanitized-event --partitions 3 --replication-factor 1
docker exec kafka-1 /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic clustered_events --partitions 3 --replication-factor 1
Write-Host "[OK] Kafka topics ready.`n" -ForegroundColor Green

# ──────────────────────────────────────────
# 2. Python / Node services
# ──────────────────────────────────────────
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Starting application services..." -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$processes = @()

# Helper: start a service in a new window
function Start-Service {
    param(
        [string]$Name,
        [string]$WorkDir,
        [string]$Command
    )
    Write-Host "[Starting] $Name" -ForegroundColor Yellow
    $proc = Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$WorkDir'; Write-Host '=== $Name ===' -ForegroundColor Green; $Command" -PassThru
    return $proc
}

# 2a. Ingestion / Webhook server (port 8000)
$processes += Start-Service -Name "Ingestion (webhook.py)" `
    -WorkDir "$ROOT\ingestion" `
    -Command "python webhook.py"

# Small delay so ports don't collide during startup
Start-Sleep -Seconds 2

# 2b. Masking service (Kafka consumer)
$processes += Start-Service -Name "Masking Service" `
    -WorkDir "$ROOT\masking" `
    -Command "python masking_service.py"

# 2c. Clustering consumer (Kafka consumer)
$processes += Start-Service -Name "Clustering Consumer" `
    -WorkDir "$ROOT\flink2.0" `
    -Command "python clustering_consumer.py"

# 2d. Summarization + API (port 8570)
$processes += Start-Service -Name "Summarization + API" `
    -WorkDir "$ROOT\summarization" `
    -Command "python summarization_consumer.py"

# 2e. Categorize Model Flask app (port 8562)
$processes += Start-Service -Name "Categorize Model (Flask)" `
    -WorkDir "$ROOT\CATEGORIZE_MODEL" `
    -Command "python app.py"

# 2f. Frontend Vite dev server (port 5173)
$processes += Start-Service -Name "Frontend (Vite)" `
    -WorkDir "$ROOT\frontend" `
    -Command "npm run dev"

# ──────────────────────────────────────────
# 3. Summary
# ──────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  All services launched!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Kafka:              localhost:9092"
Write-Host "  Kafka UI:           http://localhost:8080"
Write-Host "  Redis:              localhost:6379"
Write-Host "  Ingestion API:      http://localhost:8000"
Write-Host "  Summarization API:  http://localhost:8570"
Write-Host "  Categorize Model:   http://localhost:8562"
Write-Host "  Frontend:           http://localhost:5173"
Write-Host ""
Write-Host "Press Ctrl+C to stop all services..." -ForegroundColor Yellow
Write-Host ""

# ──────────────────────────────────────────
# 4. Wait & cleanup on Ctrl+C
# ──────────────────────────────────────────
try {
    while ($true) { Start-Sleep -Seconds 5 }
}
finally {
    Write-Host "`nShutting down..." -ForegroundColor Red

    # Kill spawned service windows
    foreach ($p in $processes) {
        if ($p -and -not $p.HasExited) {
            Write-Host "  Stopping PID $($p.Id)..." -ForegroundColor Yellow
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }

    # Stop Docker containers
    Write-Host "  Stopping Docker containers..." -ForegroundColor Yellow
    docker compose -f "$ROOT\kafka\compose.yml" down
    docker compose -f "$ROOT\masking\docker-compose.yml" down

    Write-Host "All services stopped." -ForegroundColor Green
}
