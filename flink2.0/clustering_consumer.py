"""
Pure Python Kafka consumer/producer for message clustering.
Reads from 'sanitized-event', clusters using sentence embeddings + Redis state,
and writes to 'clustered_events'.

No Flink required.
"""
import os
import json
import signal
import sys
import numpy as np
import math
from datetime import datetime
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from sentence_transformers import SentenceTransformer
import redis
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ──
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = "sanitized-event"
OUTPUT_TOPIC = "clustered_events"
CONSUMER_GROUP = "clustering_group"
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Clustering parameters
EPSILON = 0.56
LAMBDA_TIME = 0.35
TAU_SECONDS = 86400.0

# ── Globals ──
running = True


def signal_handler(sig, frame):
    global running
    print("\nShutting down gracefully...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# ── Math helpers ──

def cosine_distance(vec_a, vec_b):
    dot = float(np.dot(vec_a, vec_b))
    dot = max(-1.0, min(1.0, dot))
    return 1.0 - dot


def time_penalty(ts_a, ts_b):
    delta_seconds = abs(ts_a - ts_b)
    return LAMBDA_TIME * (1.0 - math.exp(-delta_seconds / TAU_SECONDS))


def penalised_distance(vec_a, vec_b, ts_a, ts_b):
    return cosine_distance(vec_a, vec_b) + time_penalty(ts_a, ts_b)


def parse_ts(received_at):
    if isinstance(received_at, (int, float)):
        return float(received_at)
    return datetime.fromisoformat(str(received_at)).timestamp()


# ── Redis state management ──

class ClusterState:
    """Manages cluster state in Redis, keyed per user."""

    def __init__(self, redis_client):
        self.r = redis_client

    def get_meta(self, user_id, cluster_id):
        data = self.r.get(f"cluster_meta:{user_id}:{cluster_id}")
        return json.loads(data) if data else None

    def set_meta(self, user_id, cluster_id, meta):
        self.r.set(f"cluster_meta:{user_id}:{cluster_id}", json.dumps(meta))

    def get_centroid(self, user_id, cluster_id):
        data = self.r.get(f"cluster_centroid:{user_id}:{cluster_id}")
        return np.array(json.loads(data), dtype=np.float32) if data else None

    def set_centroid(self, user_id, cluster_id, centroid):
        self.r.set(f"cluster_centroid:{user_id}:{cluster_id}",
                    json.dumps(centroid.tolist()))

    def get_all_cluster_ids(self, user_id):
        keys = self.r.keys(f"cluster_meta:{user_id}:*")
        return [k.split(':')[-1] for k in keys]

    def next_cluster_id(self, user_id):
        key = f"next_cluster_id:{user_id}"
        current = self.r.get(key)
        nid = 0 if current is None else int(current)
        self.r.set(key, str(nid + 1))
        return str(nid)


# ── Clustering logic ──

class Clusterer:
    """Embeds text and assigns events to clusters."""

    def __init__(self, state: ClusterState):
        print("Loading sentence-transformers model...")
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.state = state
        print("Model loaded.")

    def _embed(self, text):
        vec = self.embedder.encode([text], show_progress_bar=False)[0]
        norm = np.linalg.norm(vec)
        return (vec / (norm + 1e-9)).astype(np.float32)

    def _find_close_clusters(self, user_id, vec, event_ts):
        close = []
        for cid in self.state.get_all_cluster_ids(user_id):
            centroid = self.state.get_centroid(user_id, cid)
            meta = self.state.get_meta(user_id, cid)
            if centroid is None or meta is None:
                continue
            dist = penalised_distance(vec, centroid, event_ts,
                                       float(meta["centroid_time"]))
            if dist < EPSILON:
                close.append(cid)
        return close

    def _create_cluster(self, user_id, vec, event_ts):
        cid = self.state.next_cluster_id(user_id)
        self.state.set_meta(user_id, cid, {
            "member_count": 1,
            "centroid_time": event_ts,
            "last_updated": event_ts,
        })
        self.state.set_centroid(user_id, cid, vec)
        return cid

    def _update_cluster(self, user_id, cid, new_vec, event_ts):
        meta = self.state.get_meta(user_id, cid)
        centroid = self.state.get_centroid(user_id, cid)
        if meta is None or centroid is None:
            return
        n = meta["member_count"]
        new_centroid = (centroid * n + new_vec) / (n + 1)
        norm = np.linalg.norm(new_centroid)
        new_centroid = new_centroid / (norm + 1e-9)
        meta["member_count"] = n + 1
        meta["centroid_time"] = event_ts
        meta["last_updated"] = event_ts
        self.state.set_meta(user_id, cid, meta)
        self.state.set_centroid(user_id, cid, new_centroid)

    def process(self, event: dict) -> dict:
        """Assign an event to a cluster. Returns event with 'assigned_to' field."""
        user_id = (event.get("sender", {}).get("id")
                   or event.get("user_id", "unknown"))
        description = event.get("description", "")
        event_ts = parse_ts(event.get("received_at", 0))

        vec = self._embed(description)

        close_ids = self._find_close_clusters(user_id, vec, event_ts)

        if len(close_ids) == 0:
            cid = self._create_cluster(user_id, vec, event_ts)
            assigned = int(cid)
        else:
            cid = close_ids[0]
            self._update_cluster(user_id, cid, vec, event_ts)
            assigned = int(cid)

        return {**event, "assigned_to": assigned}


# ── Main loop ──

def main():
    print("=" * 50)
    print("  Clustering Service (Pure Python)")
    print(f"  Kafka: {KAFKA_BOOTSTRAP}")
    print(f"  Input:  {INPUT_TOPIC}")
    print(f"  Output: {OUTPUT_TOPIC}")
    print(f"  Redis:  {REDIS_HOST}:{REDIS_PORT}")
    print("=" * 50)

    # Connect to Redis
    redis_client = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True
    )
    redis_client.ping()
    print("✓ Redis connected")

    state = ClusterState(redis_client)
    clusterer = Clusterer(state)

    # Kafka consumer
    consumer = KafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=CONSUMER_GROUP,
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms=1000,  # poll returns after 1s if no messages
    )
    print(f"✓ Kafka consumer subscribed to '{INPUT_TOPIC}'")

    # Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        acks='all',
    )
    print(f"✓ Kafka producer ready for '{OUTPUT_TOPIC}'")
    print("\nListening for events... (Ctrl+C to stop)\n")

    count = 0
    while running:
        try:
            messages = consumer.poll(timeout_ms=1000)
            for tp, records in messages.items():
                for record in records:
                    event = record.value
                    try:
                        result = clusterer.process(event)
                        key = result.get("event_id", "")
                        producer.send(OUTPUT_TOPIC, key=key, value=result)
                        count += 1
                        print(f"[{count}] ✓ Clustered event '{result.get('event_id', '?')}' "
                              f"→ cluster {result['assigned_to']}")
                    except Exception as e:
                        print(f"✗ Error processing event: {e}")
        except Exception as e:
            if running:
                print(f"✗ Consumer error: {e}")

    # Cleanup
    print("\nFlushing producer...")
    producer.flush()
    producer.close()
    consumer.close()
    redis_client.close()
    print(f"Done. Processed {count} events total.")


if __name__ == "__main__":
    main()
