"""
Summarization service that consumes clustered events from Kafka,
groups messages per user/cluster, generates AI summaries using
OpenRouter API, and stores everything in Redis.

Redis structure per user:
    key = "user_summary:{user_id}"
    value = {
        "user_id": "...",
        "clusters": {
            "0": {
                "cluster_id": 0,
                "message_count": 5,
                "messages": [ { event_id, text, platform, timestamp }, ... ],
                "summary": "AI-generated summary of the cluster"
            },
            "1": { ... }
        }
    }

Environment variables:
    OPENROUTER_API_KEY   - Your OpenRouter API key
    OPENROUTER_MODEL     - Model name (e.g. "google/gemma-3-1b-it:free")
"""
import os
import json
import signal
import pickle
import threading
import requests
import nltk
from nltk.corpus import stopwords
from nltk.stem.porter import PorterStemmer
import string
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import uvicorn
from kafka import KafkaConsumer
import redis
from dotenv import load_dotenv

nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('stopwords', quiet=True)

load_dotenv()

# ── Configuration ──
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = "clustered_events"
CONSUMER_GROUP = "summarization_group"
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-3-1b-it:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MAX_MESSAGES_PER_CLUSTER = 200

# ── Categorization model ──
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "CATEGORIZE_MODEL")

with open(os.path.join(MODEL_DIR, "vectorizer.pkl"), "rb") as f:
    cat_vectorizer = pickle.load(f)

with open(os.path.join(MODEL_DIR, "model.pkl"), "rb") as f:
    cat_model = pickle.load(f)

CATEGORY_MAP = {4: "Important Notices", 3: "Work", 2: "Events", 1: "Personal"}

ps = PorterStemmer()


def _transform_text(text: str) -> str:
    text = text.lower()
    tokens = nltk.word_tokenize(text)
    stop = set(stopwords.words("english"))
    tokens = [ps.stem(w) for w in tokens if w.isalnum() and w not in stop and w not in string.punctuation]
    return " ".join(tokens)


def categorize_text(text: str) -> str:
    transformed = _transform_text(text)
    vectorized = cat_vectorizer.transform([transformed])
    pred = cat_model.predict(vectorized)[0]
    return CATEGORY_MAP.get(pred, "Unknown")


# ── FastAPI app ──
app = FastAPI(title="Summarization Service")

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True
        )
    return _redis_client


@app.get("/user/clusters")
def get_user_clusters(user_id: str = Query(..., description="The user ID")):
    """
    Fetch all clusters for a user, categorize each cluster using
    the categorization model, and return them grouped by category.
    """
    r = _get_redis()
    raw = r.get(f"user_summary:{user_id}")
    if not raw:
        return JSONResponse(status_code=404, content={"error": "User not found"})

    user_data = json.loads(raw)
    clusters = user_data.get("clusters", {})

    result: dict[str, list] = {}

    for cluster_id, cluster in clusters.items():
        # Use summary if available, otherwise concatenate message texts
        text = cluster.get("summary", "")
        if not text:
            text = " ".join(
                m.get("text", "") for m in cluster.get("messages", [])
            )

        category = categorize_text(text) if text.strip() else "Unknown"

        result.setdefault(category, []).append({
            "cluster_id": cluster.get("cluster_id", cluster_id),
            "message_count": cluster.get("message_count", 0),
            "summary": cluster.get("summary", ""),
            "messages": cluster.get("messages", []),
        })

    return {"user_id": user_id, "categories": result}


# ── Globals ──
running = True


def signal_handler(sig, frame):
    global running
    print("\nShutting down gracefully...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# ── Redis helpers ──

class SummaryStore:
    """Manages per-user cluster data + summaries in Redis."""

    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client

    def _key(self, user_id: str) -> str:
        return f"user_summary:{user_id}"

    def get_user_data(self, user_id: str) -> dict:
        raw = self.r.get(self._key(user_id))
        if raw:
            return json.loads(raw)
        return {"user_id": user_id, "clusters": {}}

    def save_user_data(self, user_id: str, data: dict):
        self.r.set(self._key(user_id), json.dumps(data))

    def add_message_to_cluster(self, user_id: str, cluster_id: str,
                                message: dict) -> dict:
        """
        Append a message to a cluster and return the full user data.
        Returns the updated user_data dict.
        """
        data = self.get_user_data(user_id)
        clusters = data.setdefault("clusters", {})

        if cluster_id not in clusters:
            clusters[cluster_id] = {
                "cluster_id": int(cluster_id),
                "message_count": 0,
                "messages": [],
                "summary": "",
            }

        cluster = clusters[cluster_id]
        cluster["messages"].append(message)

        # Trim to last N messages
        if len(cluster["messages"]) > MAX_MESSAGES_PER_CLUSTER:
            cluster["messages"] = cluster["messages"][-MAX_MESSAGES_PER_CLUSTER:]

        cluster["message_count"] = len(cluster["messages"])

        self.save_user_data(user_id, data)
        return data

    def update_summary(self, user_id: str, cluster_id: str, summary: str):
        data = self.get_user_data(user_id)
        if cluster_id in data.get("clusters", {}):
            data["clusters"][cluster_id]["summary"] = summary
            self.save_user_data(user_id, data)


# ── OpenRouter AI summarization ──

class Summarizer:
    """Generate summaries using OpenRouter API."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

        if not self.api_key:
            print("⚠ OPENROUTER_API_KEY not set. Summaries will be skipped.")
        else:
            print(f"✓ OpenRouter configured (model: {self.model})")

    def summarize(self, messages: list) -> str:
        """Generate a summary from a list of message dicts."""
        if not messages or not self.api_key:
            return ""

        # Build conversation text
        conversation = []
        for msg in messages:
            sender = msg.get("sender_name", "User")
            text = msg.get("text", "")
            platform = msg.get("platform", "")
            ts = msg.get("timestamp", "")
            if text:
                conversation.append(f"[{platform}] {sender} ({ts}): {text}")

        conversation_text = "\n".join(conversation)

        try:
            resp = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a strict summarizer. Your only task is to "
                                "summarize the provided chat messages in 2-4 sentences. "
                                "Preserve all names, places, and proper nouns exactly as "
                                "they appear — do not alter, redact, or treat them as "
                                "placeholders. Do not add commentary, suggestions, "
                                "disclaimers, or any content beyond the summary itself."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Summarize this cluster of messages:\n\n"
                                f"{conversation_text}"
                            ),
                        },
                    ],
                    "temperature": 0.3,
                    "max_tokens": 256,
                },
                timeout=30,
            )

            if resp.status_code == 200:
                data = resp.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                )
                return (content or "").strip()
            else:
                print(f"  ⚠ OpenRouter error {resp.status_code}: {resp.text[:200]}")
                return ""

        except requests.ConnectionError:
            print("  ⚠ Cannot reach OpenRouter API")
            return ""
        except requests.Timeout:
            print("  ⚠ OpenRouter request timed out")
            return ""


# ── Extract message info from clustered event ──

def extract_message(event: dict) -> dict:
    """Pull relevant fields from a clustered canonical event."""
    sender = event.get("sender", {})
    content = event.get("content", {})
    return {
        "event_id": event.get("event_id", ""),
        "text": content.get("text", "") if isinstance(content, dict) else "",
        "sender_name": sender.get("display_name", "Unknown") if isinstance(sender, dict) else "Unknown",
        "platform": event.get("platform", ""),
        "timestamp": event.get("received_at", ""),
    }


# ── Main loop ──

def main():
    API_PORT = int(os.getenv("SUMMARIZATION_API_PORT", 8570))

    print("=" * 55)
    print("  Summarization Service (OpenRouter)")
    print(f"  Kafka:  {KAFKA_BOOTSTRAP} → {INPUT_TOPIC}")
    print(f"  Redis:  {REDIS_HOST}:{REDIS_PORT}")
    print(f"  Model:  {OPENROUTER_MODEL}")
    print(f"  API:    http://localhost:{API_PORT}/user/clusters?user_id=...")
    print("=" * 55)

    # Connect to Redis (shared with FastAPI endpoint)
    global _redis_client
    _redis_client = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True
    )
    _redis_client.ping()
    print("✓ Redis connected")

    # Start FastAPI server in background thread
    api_thread = threading.Thread(
        target=uvicorn.run,
        kwargs={"app": app, "host": "0.0.0.0", "port": API_PORT, "log_level": "warning"},
        daemon=True,
    )
    api_thread.start()
    print(f"✓ API server running on port {API_PORT}")

    store = SummaryStore(_redis_client)
    summarizer = Summarizer(OPENROUTER_API_KEY, OPENROUTER_MODEL)

    # Kafka consumer
    consumer = KafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=CONSUMER_GROUP,
        auto_offset_reset='earliest',
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms=1000,
    )
    print(f"✓ Kafka consumer subscribed to '{INPUT_TOPIC}'")
    print("\nListening for clustered events... (Ctrl+C to stop)\n")

    count = 0
    while running:
        try:
            messages = consumer.poll(timeout_ms=1000)
            for tp, records in messages.items():
                for record in records:
                    event = record.value
                    try:
                        user_id = (event.get("sender", {}).get("id")
                                   or event.get("user_id", "unknown"))
                        cluster_id = str(event.get("assigned_to", -1))

                        # Skip noise (unassigned)
                        if cluster_id == "-1":
                            print(f"  ⊘ Skipping noise event '{event.get('event_id', '?')}'")
                            continue

                        # Extract and store message
                        msg = extract_message(event)
                        user_data = store.add_message_to_cluster(
                            user_id, cluster_id, msg
                        )

                        cluster = user_data["clusters"][cluster_id]
                        count += 1
                        print(f"[{count}] ✓ Added to user={user_id} "
                              f"cluster={cluster_id} "
                              f"(msgs: {cluster['message_count']})")

                        # Re-summarize this cluster
                        print(f"  → Summarizing cluster {cluster_id}...")
                        summary = summarizer.summarize(cluster["messages"])

                        if summary:
                            store.update_summary(user_id, cluster_id, summary)
                            print(f"  → Summary: {summary[:100]}...")
                        else:
                            print(f"  → No summary generated")

                    except Exception as e:
                        print(f"✗ Error processing event: {e}")

        except Exception as e:
            if running:
                print(f"✗ Consumer error: {e}")

    # Cleanup
    consumer.close()
    _redis_client.close()
    print(f"\nDone. Processed {count} events total.")


if __name__ == "__main__":
    main()
