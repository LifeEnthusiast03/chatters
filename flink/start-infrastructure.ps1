# Quick start script for the clustering system
# Run this from PowerShell

Write-Host "=== Starting Clustering System ===" -ForegroundColor Green

# Check if Redis is running
Write-Host "`nChecking Redis..." -ForegroundColor Yellow
$redisRunning = docker ps --filter "name=redis" --format "{{.Names}}" | Select-String -Pattern "redis"
if (-not $redisRunning) {
    Write-Host "Starting Redis..." -ForegroundColor Yellow
    docker run -d -p 6379:6379 --name redis --network double-slash-net redis:latest
    Start-Sleep -Seconds 3
} else {
    Write-Host "Redis already running" -ForegroundColor Green
}

# Check if Kafka is running
Write-Host "`nChecking Kafka..." -ForegroundColor Yellow
$kafkaRunning = docker ps --filter "name=kafka-1" --format "{{.Names}}" | Select-String -Pattern "kafka"
if (-not $kafkaRunning) {
    Write-Host "Starting Kafka..." -ForegroundColor Yellow
    Push-Location ..\kafka
    docker-compose up -d
    Pop-Location
    Write-Host "Waiting for Kafka to be ready (30s)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 30
} else {
    Write-Host "Kafka already running" -ForegroundColor Green
}

Write-Host "`n=== Infrastructure Ready ===" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "1. Start Python service: python clustering_service.py"
Write-Host "2. Build Flink job: mvn clean package"
Write-Host "3. Run Flink job: java -cp target/flink-clustering-1.0-SNAPSHOT.jar com.chatters.flink.ClusteringJob"
Write-Host "`nOr run them manually in separate terminals"
