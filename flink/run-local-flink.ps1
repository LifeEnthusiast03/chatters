# Download and run Flink locally with the clustering job

$FLINK_VERSION = "1.18.0"
$FLINK_SCALA = "2.12"
$FLINK_DIR = "flink-$FLINK_VERSION"
$FLINK_ARCHIVE = "flink-$FLINK_VERSION-bin-scala_$FLINK_SCALA.tgz"
$FLINK_URL = "https://archive.apache.org/dist/flink/flink-$FLINK_VERSION/$FLINK_ARCHIVE"

# Check if Flink is already downloaded
if (-not (Test-Path $FLINK_DIR)) {
    Write-Host "Downloading Flink $FLINK_VERSION..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $FLINK_URL -OutFile $FLINK_ARCHIVE
    
    Write-Host "Extracting Flink..." -ForegroundColor Yellow
    tar -xzf $FLINK_ARCHIVE
    
    Write-Host "Cleaning up archive..." -ForegroundColor Yellow
    Remove-Item $FLINK_ARCHIVE
}

Write-Host "`nStarting Flink local cluster..." -ForegroundColor Green
Start-Process -FilePath "$FLINK_DIR\bin\start-cluster.bat" -NoNewWindow

Write-Host "Waiting for Flink to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host "`nSubmitting job..." -ForegroundColor Green
& "$FLINK_DIR\bin\flink.bat" run target\flink-clustering-1.0-SNAPSHOT.jar

Write-Host "`nJob submitted. Check Flink Web UI at http://localhost:8081" -ForegroundColor Cyan
Write-Host "`nTo stop Flink cluster later, run: $FLINK_DIR\bin\stop-cluster.bat" -ForegroundColor Yellow
