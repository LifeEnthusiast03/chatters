"""Kafka producer module for sending canonical events to Kafka"""
import os
import json
from kafka import KafkaProducer
from kafka.errors import KafkaError
from pymodel import CanonicalEvent
from dotenv import load_dotenv

load_dotenv()

# Kafka configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = "raw-chat-stream"

# Initialize Kafka producer (singleton pattern)
_producer = None


def get_kafka_producer():
    """Get or create Kafka producer instance"""
    global _producer
    if _producer is None:
        _producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',  # Wait for all replicas to acknowledge
            retries=3,
            max_in_flight_requests_per_connection=1
        )
    return _producer


def send_to_kafka(canonical_event: CanonicalEvent) -> bool:
    """
    Send a canonical event to Kafka topic 'raw-chat-stream'
    
    Args:
        canonical_event: CanonicalEvent object to send
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        producer = get_kafka_producer()
        
        # Convert CanonicalEvent to dict
        event_dict = canonical_event.model_dump(mode='json')
        
        # Use event_id as the key for partitioning
        key = canonical_event.event_id
        
        # Send to Kafka
        future = producer.send(
            topic=KAFKA_TOPIC,
            key=key,
            value=event_dict
        )
        
        # Block for 'synchronous' send (optional, can be removed for async)
        record_metadata = future.get(timeout=10)
        
        print(f"✓ Sent to Kafka topic '{record_metadata.topic}' "
              f"[partition: {record_metadata.partition}, offset: {record_metadata.offset}]")
        
        return True
        
    except KafkaError as e:
        print(f"✗ Kafka error sending message: {e}")
        return False
    except Exception as e:
        print(f"✗ Error sending to Kafka: {e}")
        return False


def close_kafka_producer():
    """Close the Kafka producer connection"""
    global _producer
    if _producer is not None:
        _producer.flush()
        _producer.close()
        _producer = None
        print("Kafka producer closed")
