# Build and run Flink job locally (standalone mode)
# This builds a fat JAR with all dependencies included

Write-Host "=== Building Flink Job (Local Profile) ===" -ForegroundColor Green
mvn clean package -Plocal

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=== Build Successful ===" -ForegroundColor Green
    Write-Host "`n=== Running Flink Job ===" -ForegroundColor Cyan
    Write-Host "Make sure Python clustering service is running on http://localhost:5000`n" -ForegroundColor Yellow
    
    java -jar target/flink-clustering-1.0-SNAPSHOT.jar
} else {
    Write-Host "`n=== Build Failed ===" -ForegroundColor Red
    Write-Host "Check the error messages above and ensure you have Java 11+ and Maven installed" -ForegroundColor Yellow
}
