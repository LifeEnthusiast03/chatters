# Create required Kafka topics for the clustering pipeline

Write-Host "=== Creating Kafka Topics ===" -ForegroundColor Green

$topics = @(
    "raw-chat-stream",
    "sanitized-event",
    "clustered_events"
)

foreach ($topic in $topics) {
    Write-Host "`nCreating topic: $topic" -ForegroundColor Yellow
    docker exec kafka-1 /opt/kafka/bin/kafka-topics.sh `
        --bootstrap-server localhost:9092 `
        --create `
        --if-not-exists `
        --topic $topic `
        --partitions 3 `
        --replication-factor 1
}

Write-Host "`n=== Listing all topics ===" -ForegroundColor Cyan
docker exec kafka-1 /opt/kafka/bin/kafka-topics.sh `
    --bootstrap-server localhost:9092 `
    --list

Write-Host "`n=== Topics ready! ===" -ForegroundColor Green
