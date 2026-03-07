# Flink Clustering System

This system performs real-time message clustering using:
- **Java Flink** for stream processing (reads from Kafka, manages state)
- **Python Flask service** for ML clustering logic (embeddings + DBSCAN)
- **Redis** for state storage (cluster centroids and metadata)

## Quick Start (3 Commands)

```powershell
# 1. Start infrastructure (in Terminal 1)
cd "e:\double slash\chatters\flink"
.\start-infrastructure.ps1

# 2. Start Python service (in Terminal 2)
pip install -r requirements.txt
python clustering_service.py

# 3. Run Flink job (in Terminal 3)
.\build-and-run-local.ps1
```

Done! Messages from `sanitized-event` topic will be clustered and written to `clustered_events`.

---

## Architecture

```
Kafka (sanitized-event) 
    → Flink Job (Java)
        → HTTP call → Python Clustering Service
            → Redis (state storage)
    → Kafka (clustered_events)
```

## Prerequisites

1. **Java 11+** (for Flink)
2. **Maven** (for building Java project)
3. **Python 3.8+** with pip
4. **Docker** (for Kafka and Redis)

## Setup

### 1. Start Infrastructure

```powershell
# Start Kafka
cd "e:\double slash\chatters\kafka"
docker-compose up -d

# Start Redis
docker run -d -p 6379:6379 --name redis redis:latest
```

### 2. Install Python Dependencies

```powershell
cd "e:\double slash\chatters\flink"
pip install -r requirements.txt
```

### 3. Build Java Flink Job

**For local standalone execution (easiest):**
```powershell
cd "e:\double slash\chatters\flink"
mvn clean package -Plocal
```

**For Flink cluster submission:**
```powershell
cd "e:\double slash\chatters\flink"
mvn clean package
```

The `-Plocal` profile creates a fat JAR with all dependencies included.

## Running

### Step 1: Start Python Clustering Service

```powershell
cd "e:\double slash\chatters\flink"
python clustering_service.py
```

Service runs on **http://localhost:5000**

Test it:
```powershell
curl -X POST http://localhost:5000/cluster `
  -H "Content-Type: application/json" `
  -d '{"user_id": "test", "description": "hello world", "received_at": 1234567890}'
```

### Step 2: Run Flink Job

**Option A: Standalone local execution (EASIEST)**

```powershell
# One command to build and run:
.\build-and-run-local.ps1

# Or manually:
mvn clean package -Plocal
java -jar target/flink-clustering-1.0-SNAPSHOT.jar
```

This runs Flink embedded in the Java process.

**Option B: Using local Flink installation**

```powershell
.\run-local-flink.ps1
```

This downloads Flink, starts a local cluster, and submits the job.

**Option C: Submit to Docker Flink cluster**

```powershell
# Build for cluster submission (without -Plocal)
mvn clean package

# Start Flink cluster
docker-compose up -d

# Wait for cluster to be ready (check http://localhost:8081)

# Copy JAR to container and submit
docker cp target/flink-clustering-1.0-SNAPSHOT.jar flink-jobmanager:/tmp/
docker exec flink-jobmanager flink run /tmp/flink-clustering-1.0-SNAPSHOT.jar
```
```

## Testing

### 1. Send test message to Kafka

```powershell
docker exec -it kafka-1 /opt/kafka/bin/kafka-console-producer.sh `
  --bootstrap-server localhost:9092 `
  --topic sanitized-event
```

Paste this JSON:
```json
{"sender":{"id":"user123","display_name":"John"},"description":"Server is down","received_at":"2026-03-07T10:00:00"}
```

### 2. Watch output

```powershell
docker exec -it kafka-1 /opt/kafka/bin/kafka-console-consumer.sh `
  --bootstrap-server localhost:9092 `
  --topic clustered_events `
  --from-beginning
```

You should see the event with `"assigned_to": 0` (cluster ID).

## Configuration

### Kafka Topics
- **Input**: `sanitized-event`
- **Output**: `clustered_events`

### Clustering Parameters (in clustering_service.py)
- `EPSILON = 0.56` - Distance threshold for clustering
- `LAMBDA_TIME = 0.35` - Time decay weight
- `TAU_SECONDS = 86400.0` - Time decay constant (1 day)

### Flink Job Parameters (in ClusteringJob.java)
- `KAFKA_BROKERS = "localhost:9092"`
- `PYTHON_SERVICE_URL = "http://localhost:5000/cluster"`

## Monitoring

### Flink Web UI
- URL: http://localhost:8081
- Shows job status, metrics, backpressure

### Python Service Logs
- Check terminal where `clustering_service.py` is running
- Shows incoming requests and clustering decisions

### Redis
```powershell
docker exec -it redis redis-cli
KEYS *
GET cluster_meta:user123:0
```

## Troubleshooting

### Python service not responding
```powershell
# Check if running
curl http://localhost:5000/health
```

### Redis connection failed
```powershell
docker ps | grep redis
docker logs redis
```

### Flink job fails
- Check Flink logs in Web UI
- Ensure Kafka topics exist
- Ensure Python service is running

### Build errors
```powershell
# Clean and rebuild
mvn clean package -U
```

## Stopping

```powershell
# Stop Python service: Ctrl+C

# Stop Flink
docker-compose down

# Stop Redis
docker stop redis
docker rm redis

# Stop Kafka
cd ../kafka
docker-compose down
```
