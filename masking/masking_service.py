import json
import hashlib
import os
from kafka import KafkaConsumer, KafkaProducer
from presidio_analyzer import AnalyzerEngine
import redis
from typing import Optional

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = "raw-chat-stream"
OUTPUT_TOPIC = "sanitized-event"
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

class HashPIIAnonymizer:
    def __init__(self, salt="my_secret_salt", redis_client: Optional[redis.Redis] = None):
        self.analyzer = AnalyzerEngine()
        self.salt = salt
        self.redis_client = redis_client

    def _hash_value(self, value: str):
        """
        Create deterministic hash for PII value
        """
        h = hashlib.sha256((value + self.salt).encode()).hexdigest()
        return h[:12]  # shorter hash for readability

    def anonymize(self, text: str):
        if not text:
            return text

        results = self.analyzer.analyze(
            text=text,
            entities=None,
            language="en"
        )
        # Filter overlapping entities by keeping highest score first
        results = sorted(results, key=lambda x: x.score, reverse=True)
        keep_results = []
        occupied_ranges = []

        for r in results:
            is_overlapping = False
            for start, end in occupied_ranges:
                if max(r.start, start) < min(r.end, end):
                    is_overlapping = True
                    break
            if not is_overlapping:
                keep_results.append(r)
                occupied_ranges.append((r.start, r.end))

        # replace from right → left to avoid index shifting issues
        results = sorted(keep_results, key=lambda x: x.start, reverse=True)

        anonymized_text = text

        for r in results:
            value = text[r.start:r.end]
            hash_value = self._hash_value(value)
            
            # Format: ENTITY_TYPE_HASH -> PERSON_a1b2c3d4e5f6
            token = f"<{r.entity_type}_{hash_value}>"

            # Store mapping in Redis (Key: Token, Value: Original PII)
            if self.redis_client:
                # Key expiration can be set here if needed (e.g., ex=86400 for 24h)
                self.redis_client.set(token, value)

            anonymized_text = (
                anonymized_text[:r.start]
                + token
                + anonymized_text[r.end:]
            )

        return anonymized_text

def process_messages():
    # Initialize Redis connection
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        r.ping() # Check connection
        print(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    except redis.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
        return

    # Initialize Anonymizer
    anonymizer = HashPIIAnonymizer(redis_client=r)

    # Initialize Kafka Consumer
    consumer = KafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='pii-masking-group',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    # Initialize Kafka Producer
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda x: json.dumps(x).encode('utf-8')
    )

    print(f"Listening for messages on {INPUT_TOPIC}...")

    for message in consumer:
        event = message.value
        
        # Check if it looks like a CanonicalEvent and has a description
        if isinstance(event, dict):
            description = event.get("description")
            
            if description:
                original_text = description
                masked_text = anonymizer.anonymize(original_text)
                
                # Update the event with masked description
                event["description"] = masked_text
                
                # Also mask content.text if it exists, as it might contain PII too
                if "content" in event and event["content"] and "text" in event["content"]:
                     if event["content"]["text"]:
                        event["content"]["text"] = anonymizer.anonymize(event["content"]["text"])

                print(f"Original: {original_text}")
                print(f"Masked:   {masked_text}")
                
                # Send to output topic
                producer.send(OUTPUT_TOPIC, value=event)
                print(f"Sent sanitized event to {OUTPUT_TOPIC}")
            else:
                # Pass through events without description field (or maybe log valid warning)
                producer.send(OUTPUT_TOPIC, value=event)
        else:
             print(f"Received non-dict message: {event}")

if __name__ == "__main__":
    process_messages()
