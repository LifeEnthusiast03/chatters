"""
Python clustering service that can be called from Java Flink
Runs as a Flask REST API
"""
import json
import numpy as np
import math
from datetime import datetime
from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer
import redis

app = Flask(__name__)

# Initialize embedder
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Redis client for state management
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Clustering parameters
EPSILON = 0.56
MIN_PTS = 1
LAMBDA_TIME = 0.35
TAU_SECONDS = 86400.0


def cosine_distance(vec_a, vec_b):
    """Calculate cosine distance between two vectors"""
    dot = float(np.dot(vec_a, vec_b))
    dot = max(-1.0, min(1.0, dot))
    return 1.0 - dot


def time_penalty(ts_a, ts_b):
    """Calculate time decay penalty"""
    delta_seconds = abs(ts_a - ts_b)
    return LAMBDA_TIME * (1.0 - math.exp(-delta_seconds / TAU_SECONDS))


def penalised_distance(vec_a, vec_b, ts_a, ts_b):
    """Calculate distance with time penalty"""
    return cosine_distance(vec_a, vec_b) + time_penalty(ts_a, ts_b)


def embed_and_normalise(description):
    """Generate normalized embedding for text"""
    vec = embedder.encode([description], show_progress_bar=False)[0]
    norm = np.linalg.norm(vec)
    return (vec / (norm + 1e-9)).astype(np.float32)


def parse_ts(received_at):
    """Parse timestamp from various formats"""
    if isinstance(received_at, (int, float)):
        return float(received_at)
    return datetime.fromisoformat(str(received_at)).timestamp()


def get_cluster_meta(user_id, cluster_id):
    """Get cluster metadata from Redis"""
    key = f"cluster_meta:{user_id}:{cluster_id}"
    data = redis_client.get(key)
    return json.loads(data) if data else None


def set_cluster_meta(user_id, cluster_id, meta):
    """Store cluster metadata in Redis"""
    key = f"cluster_meta:{user_id}:{cluster_id}"
    redis_client.set(key, json.dumps(meta))


def get_cluster_centroid(user_id, cluster_id):
    """Get cluster centroid from Redis"""
    key = f"cluster_centroid:{user_id}:{cluster_id}"
    data = redis_client.get(key)
    return np.array(json.loads(data), dtype=np.float32) if data else None


def set_cluster_centroid(user_id, cluster_id, centroid):
    """Store cluster centroid in Redis"""
    key = f"cluster_centroid:{user_id}:{cluster_id}"
    redis_client.set(key, json.dumps(centroid.tolist()))


def get_all_cluster_ids(user_id):
    """Get all cluster IDs for a user"""
    pattern = f"cluster_meta:{user_id}:*"
    keys = redis_client.keys(pattern)
    return [key.split(':')[-1] for key in keys]


def get_next_cluster_id(user_id):
    """Get next cluster ID for a user"""
    key = f"next_cluster_id:{user_id}"
    current = redis_client.get(key)
    next_id = 0 if current is None else int(current)
    redis_client.set(key, str(next_id + 1))
    return str(next_id)


def find_close_clusters(user_id, vec, event_ts):
    """Find clusters within EPSILON distance"""
    close = []
    cluster_ids = get_all_cluster_ids(user_id)
    
    for cluster_id in cluster_ids:
        centroid = get_cluster_centroid(user_id, cluster_id)
        if centroid is None:
            continue
            
        meta = get_cluster_meta(user_id, cluster_id)
        if meta is None:
            continue
            
        centroid_ts = float(meta["centroid_time"])
        dist = penalised_distance(vec, centroid, event_ts, centroid_ts)
        
        if dist < EPSILON:
            close.append(cluster_id)
    
    return close


def create_cluster(user_id, vec, event_ts):
    """Create a new cluster"""
    cluster_id = get_next_cluster_id(user_id)
    
    meta = {
        "member_count": 1,
        "centroid_time": event_ts,
        "last_updated": event_ts,
    }
    
    set_cluster_meta(user_id, cluster_id, meta)
    set_cluster_centroid(user_id, cluster_id, vec)
    
    return cluster_id


def update_cluster(user_id, cluster_id, new_vec, event_ts):
    """Update existing cluster with new vector"""
    meta = get_cluster_meta(user_id, cluster_id)
    centroid = get_cluster_centroid(user_id, cluster_id)
    
    if meta is None or centroid is None:
        return
    
    n = meta["member_count"]
    
    # Update centroid
    new_centroid = (centroid * n + new_vec) / (n + 1)
    norm = np.linalg.norm(new_centroid)
    new_centroid = new_centroid / (norm + 1e-9)
    
    # Update metadata
    meta["member_count"] = n + 1
    meta["centroid_time"] = event_ts
    meta["last_updated"] = event_ts
    
    set_cluster_meta(user_id, cluster_id, meta)
    set_cluster_centroid(user_id, cluster_id, new_centroid)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200


@app.route('/cluster', methods=['POST'])
def cluster_event():
    """
    Cluster an event
    Expected JSON: {
        "user_id": "string",
        "description": "string",
        "received_at": "timestamp or ISO string"
    }
    Returns: {
        "assigned_to": int (cluster_id or -1 for noise)
    }
    """
    try:
        event = request.get_json()
        
        user_id = event.get("user_id")
        description = event.get("description", "")
        received_at = event.get("received_at")
        
        if not user_id or not description:
            return jsonify({"error": "Missing user_id or description"}), 400
        
        # Parse timestamp
        event_ts = parse_ts(received_at)
        
        # Generate embedding
        vec = embed_and_normalise(description)
        
        # Find close clusters
        close_ids = find_close_clusters(user_id, vec, event_ts)
        
        if len(close_ids) == 0:
            # No close clusters - create new one
            cluster_id = create_cluster(user_id, vec, event_ts)
            assigned = int(cluster_id)
        else:
            # Assign to closest cluster (first one)
            cluster_id = close_ids[0]
            update_cluster(user_id, cluster_id, vec, event_ts)
            assigned = int(cluster_id)
        
        return jsonify({"assigned_to": assigned}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("Starting Python Clustering Service...")
    print("Make sure Redis is running on localhost:6379")
    app.run(host='0.0.0.0', port=5000, debug=False)
