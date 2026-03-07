import json
import redis
import os
from kafka import KafkaConsumer
from datetime import datetime

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = "clustered_events"
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Time to Live for clusters (7 days in seconds)
CLUSTER_TTL_SECONDS = 7 * 24 * 3600

def process_clustered_events():
    # Initialize Redis connection
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        r.ping()
        print(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    except redis.ConnectionError as e:
        print(f"Failed to connect to Redis: {e}")
        return

    # Initialize Kafka Consumer
    consumer = KafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset='latest',
        enable_auto_commit=True,
        group_id='cluster-storage-consumer',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    print(f"Listening for clustered events on {INPUT_TOPIC}...")

    for message in consumer:
        event = message.value
        
        # Extract key fields
        try:
            # We now use the top-level 'user_id' for partitioning
            user_id = event["user_id"]
            cluster_id = event["assigned_to"]
            description = event.get("description", "")
            received_at = event.get("received_at")
            event_id = event.get("event_id") or str(datetime.now().timestamp())
            
            # Skip noise (-1) if you don't want to store it, or store it in a special "noise" cluster
            if cluster_id == -1:
                # Optional: handle noise specifically if needed
                continue

            # ---------------------------------------------------------
            # Redis Data Structure Strategy:
            # 1. Cluster Metadata (Hash): Stores info about the cluster itself (count, last_update)
            #    Key: cluster:{user_id}:{cluster_id}:meta
            #
            # 2. Cluster Content (List/Stream): Stores the actual messages in the cluster
            #    Key: cluster:{user_id}:{cluster_id}:messages
            #
            # 3. User Index (Set): Keeps track of which clusters a user has
            #    Key: user:{user_id}:clusters
            # ---------------------------------------------------------

            cluster_meta_key = f"cluster:{user_id}:{cluster_id}:meta"
            cluster_msgs_key = f"cluster:{user_id}:{cluster_id}:messages"
            user_index_key   = f"user:{user_id}:clusters"

            pipeline = r.pipeline()

            # 1. Update Cluster Metadata (bump last_updated)
            # We can store simple stats here. The Flink job is the source of truth for the centroid,
            # but this consumer manages the "view" of the cluster content.
            pipeline.hset(cluster_meta_key, mapping={
                "last_updated": received_at,
                "user_id": user_id,
                "cluster_id": cluster_id
            })
            # Refresh TTL for metadata
            pipeline.expire(cluster_meta_key, CLUSTER_TTL_SECONDS)


            # 2. Store the Message in the Cluster
            # We store a compact JSON of the message.
            # Using LPUSH to add to a list. You could also use Redis Streams (XADD) for more advanced features.
            msg_data = json.dumps({
                "processed_at": datetime.now().isoformat(),
                "description": description,
                "original_event": event
            })
            pipeline.lpush(cluster_msgs_key, msg_data)
            
            # Optional: Cap the list size to prevent infinite growth (e.g., keep last 50 messages)
            # pipeline.ltrim(cluster_msgs_key, 0, 49)
            
            # Refresh TTL for the message list
            pipeline.expire(cluster_msgs_key, CLUSTER_TTL_SECONDS)


            # 3. Update User Index
            # Add this cluster_id to the user's set of active clusters
            pipeline.sadd(user_index_key, cluster_id)
            # We typically don't expire the user index itself, or set a very long TTL (e.g. 30 days)
            # because a user might have other clusters that are still valid.
            # However, if you want users to "disappear" after inactivity:
            pipeline.expire(user_index_key, CLUSTER_TTL_SECONDS) 

            pipeline.execute()
            
            print(f"Stored message for User {user_id} in Cluster {cluster_id}")

        except KeyError as e:
            print(f"Skipping malformed event: missing {e}")
        except Exception as e:
            print(f"Error processing event: {e}")

if __name__ == "__main__":
    process_clustered_events()
