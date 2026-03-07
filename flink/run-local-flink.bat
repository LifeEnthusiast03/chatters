@echo off
REM Download and run Flink locally with the clustering job

SET FLINK_VERSION=1.18.0
SET FLINK_SCALA=2.12
SET FLINK_DIR=flink-%FLINK_VERSION%

REM Check if Flink is already downloaded
if not exist %FLINK_DIR% (
    echo Downloading Flink %FLINK_VERSION%...
    curl -O https://archive.apache.org/dist/flink/flink-%FLINK_VERSION%/flink-%FLINK_VERSION%-bin-scala_%FLINK_SCALA%.tgz
    
    echo Extracting Flink...
    tar -xzf flink-%FLINK_VERSION%-bin-scala_%FLINK_SCALA%.tgz
    
    echo Cleaning up archive...
    del flink-%FLINK_VERSION%-bin-scala_%FLINK_SCALA%.tgz
)

echo.
echo Starting Flink local cluster...
start /B %FLINK_DIR%\bin\start-cluster.bat

echo Waiting for Flink to start...
timeout /t 10 /nobreak > nul

echo.
echo Submitting job...
%FLINK_DIR%\bin\flink.bat run target\flink-clustering-1.0-SNAPSHOT.jar

echo.
echo Job submitted. Check Flink Web UI at http://localhost:8081
echo.
echo To stop Flink cluster later, run: %FLINK_DIR%\bin\stop-cluster.bat
