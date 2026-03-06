from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.functions import KeyedProcessFunction, RuntimeContext
from pyflink.datastream.state import ValueStateDescriptor, ListStateDescriptor, MapStateDescriptor
from pyflink.common.typeinfo import Types
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaSink, KafkaRecordSerializationSchema, DeliveryGuarantee, OffsetsInitializer
from pyflink.common.watermark_strategy import WatermarkStrategy
import json
import numpy as np
import math
from datetime import datetime



EPSILON     = 0.56       # threshold on the time-penalised distance
MIN_PTS     = 1          # minimum cluster size before a noise point is absorbed

# Time decay: final_dist = cosine_dist + λ*(1 - exp(-Δt/τ))
# τ = 86400s (24h) — half-life of temporal relevance
# λ = 0.35  — max contribution of time penalty (caps asymptotically)
# At Δt=0      → penalty=0.000   
# At Δt=6h     → penalty=0.086   
# At Δt=24h    → penalty=0.221   
# At Δt=72h    → penalty=0.315   
# At Δt=∞      → penalty=0.350   
LAMBDA_TIME = 0.35
TAU_SECONDS = 86400.0



def cosine_distance(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Cosine distance between two L2-normalised vectors.
    Both centroids and incoming vecs are kept normalised, so this is
    equivalent to 1 - dot(a, b), but we compute it explicitly for clarity.
    """
    dot = float(np.dot(vec_a, vec_b))
    # clamp to [-1, 1] to guard against floating-point drift
    dot = max(-1.0, min(1.0, dot))
    return 1.0 - dot


def time_penalty(ts_a: float, ts_b: float) -> float:
    """
    Exponential decay penalty based on the time gap between two events.
        penalty = λ * (1 - exp(-|Δt| / τ))
    Smooth, continuous, no conditionals.
    Caps at λ so it never overwhelms strong semantic similarity.

    Args:
        ts_a: Unix timestamp (seconds) of event A
        ts_b: Unix timestamp (seconds) of event B
    """
    delta_seconds = abs(ts_a - ts_b)
    return LAMBDA_TIME * (1.0 - math.exp(-delta_seconds / TAU_SECONDS))


def penalised_distance(
    vec_a: np.ndarray,
    vec_b: np.ndarray,
    ts_a: float,
    ts_b: float,
) -> float:
    """
    Combined semantic + temporal distance. Identical logic to Code 1.
        final_dist = cosine_dist + λ*(1 - exp(-|Δt|/τ))
    """
    return cosine_distance(vec_a, vec_b) + time_penalty(ts_a, ts_b)


def embed_and_normalise(embedder, description: str) -> np.ndarray:
    """
    Embed a string and L2-normalise the result.
    Identical to the embed() function in Code 1.
    """
    vec  = embedder.encode([description], show_progress_bar=False)[0]
    norm = np.linalg.norm(vec)
    return (vec / (norm + 1e-9)).astype(np.float32)


def parse_ts(received_at) -> float:
    """
    Convert received_at (ISO string or Unix float) to a Unix timestamp float.
    Flink events carry received_at as an ISO-8601 string.
    """
    if isinstance(received_at, (int, float)):
        return float(received_at)
    return datetime.fromisoformat(str(received_at)).timestamp()


# ─── PyFlink Operator ─────────────────────────────────────────────────────────

class ClusteringProcessFunction(KeyedProcessFunction):
   

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def open(self, runtime_context: RuntimeContext):
        self.cluster_meta = runtime_context.get_map_state(
            MapStateDescriptor(
                "cluster_meta",
                Types.STRING(),   # cluster_id (str of int)
                Types.STRING()    # JSON: {member_count, centroid_time, last_updated}
            )
        )

        self.cluster_centroids = runtime_context.get_map_state(
            MapStateDescriptor(
                "cluster_centroids",
                Types.STRING(),   # cluster_id
                Types.STRING()    # JSON array of 384 floats
            )
        )

        # Each noise item: {"vec": [...], "event": {...}}
        self.noise_buffer = runtime_context.get_list_state(
            ListStateDescriptor(
                "noise_buffer",
                Types.STRING()    # JSON-serialised noise item
            )
        )

        # Monotonic counter for cluster IDs, mirrors self._next_id in Code 1
        self.next_cluster_id = runtime_context.get_state(
            ValueStateDescriptor("next_cluster_id", Types.INT())
        )

        # Load the embedding model ONCE per TaskManager worker.
        # open() is called once when the operator is initialised, not per event.
        from sentence_transformers import SentenceTransformer
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")

    # ── Main processing ───────────────────────────────────────────────────────

    def process_element(self, event: dict, ctx: KeyedProcessFunction.Context):
        """
        Called for every incoming message. Mirrors CentroidClusterer.ingest().
        """
        description = event.get("description", "")
        received_at = event.get("received_at")
        event_ts    = parse_ts(received_at)

        # Embed + normalise — CPU only, no I/O
        vec = embed_and_normalise(self.embedder, description)

        # ── Bootstrap: first event ever for this user ──────────────────────
        has_clusters = any(True for _ in self.cluster_meta.keys())
        noise_list   = list(self.noise_buffer.get() or [])
        has_noise    = len(noise_list) > 0

        if not has_clusters and not has_noise:
            # Identical to Code 1: first item always goes to noise
            self._add_to_noise(vec, event, noise_list)
            yield {**event, "assigned_to": -1}
            return

        close_ids = self._find_close_clusters(vec, event_ts)

        if len(close_ids) == 0:
            self._add_to_noise(vec, event, noise_list)
            assigned = -1

        elif len(close_ids) == 1:
            self._update_cluster(close_ids[0], vec, event_ts)
            assigned = int(close_ids[0])

        else:
            # Merge all matching clusters into the lowest-id survivor
            survivor_id = str(min(int(cid) for cid in close_ids))
            for cid in close_ids:
                if cid != survivor_id:
                    self._merge_clusters(survivor_id, cid)
            self._update_cluster(survivor_id, vec, event_ts)
            assigned = int(survivor_id)

        noise_list = list(self.noise_buffer.get() or [])
        noise_list = self._recheck_noise(noise_list)

        noise_list = self._promote_noise(noise_list)

        # Persist the updated noise buffer back to Flink state
        self.noise_buffer.clear()
        for item in noise_list:
            self.noise_buffer.add(item)

        # Optionally register a TTL timer so idle clusters get flushed later
        if assigned != -1:
            expiry_ts = ctx.timestamp() + (7 * 24 * 3600 * 1000)  # 7 days in ms
            ctx.timer_service().register_processing_time_timer(expiry_ts)

        yield {**event, "assigned_to": assigned}

    # ── Timer (TTL / flush) ───────────────────────────────────────────────────

    def on_timer(self, timestamp: int, ctx: KeyedProcessFunction.OnTimerContext):
        """
        Called when a cluster's TTL expires (no new messages for 7 days).
        Flush settled clusters to Cassandra for long-term storage.
        """
        for cluster_id in list(self.cluster_meta.keys()):
            meta         = json.loads(self.cluster_meta.get(cluster_id))
            last_updated = meta["last_updated"]
            age_ms       = timestamp - last_updated
            if age_ms > 7 * 24 * 3600 * 1000:
                self._flush_cluster_to_cassandra(cluster_id, meta)
                self.cluster_meta.remove(cluster_id)
                self.cluster_centroids.remove(cluster_id)

    # ── Cluster helpers ───────────────────────────────────────────────────────

    def _get_next_id(self) -> str:
        """Atomically increment and return the next cluster ID as a string."""
        current = self.next_cluster_id.value()
        nid     = 0 if current is None else current
        self.next_cluster_id.update(nid + 1)
        return str(nid)

    def _find_close_clusters(self, vec: np.ndarray, event_ts: float) -> list:
        """
        Return list of cluster_ids whose penalised distance to vec < EPSILON.
        O(k) — one distance computation per cluster centroid.
        """
        close = []
        for cluster_id in self.cluster_meta.keys():
            centroid    = np.array(json.loads(self.cluster_centroids.get(cluster_id)),
                                   dtype=np.float32)
            meta        = json.loads(self.cluster_meta.get(cluster_id))
            centroid_ts = float(meta["centroid_time"])
            dist        = penalised_distance(vec, centroid, event_ts, centroid_ts)
            if dist < EPSILON:
                close.append(cluster_id)
        return close

    def _create_cluster(self, vec: np.ndarray, event: dict, event_ts: float) -> str:
        """
        Create a brand-new cluster from a single event.
        Mirrors Cluster.__init__() in Code 1.
        """
        cid  = self._get_next_id()
        meta = {
            "member_count" : 1,
            "centroid_time": event_ts,
            "last_updated" : event_ts,
        }
        self.cluster_meta.put(cid, json.dumps(meta))
        self.cluster_centroids.put(cid, json.dumps(vec.tolist()))
        return cid

    def _update_cluster(self, cluster_id: str, new_vec: np.ndarray, event_ts: float):
        """
        Incremental centroid update. Mirrors Cluster.add() in Code 1:
            new_centroid = (old_centroid * n + new_vec) / (n + 1)  then re-normalise
            centroid_time updated as running average of timestamps
        """
        meta     = json.loads(self.cluster_meta.get(cluster_id))
        centroid = np.array(json.loads(self.cluster_centroids.get(cluster_id)),
                            dtype=np.float32)
        n = meta["member_count"]

        # Weighted average centroid update — O(1)
        new_centroid  = (centroid * n + new_vec) / (n + 1)
        norm          = np.linalg.norm(new_centroid)
        new_centroid  = new_centroid / (norm + 1e-9)

        # Running average of timestamps
        old_ct            = float(meta["centroid_time"])
        new_ct            = (old_ct * n + event_ts) / (n + 1)

        meta["member_count"]  = n + 1
        meta["centroid_time"] = new_ct
        meta["last_updated"]  = event_ts

        self.cluster_meta.put(cluster_id, json.dumps(meta))
        self.cluster_centroids.put(cluster_id, json.dumps(new_centroid.tolist()))

    def _merge_clusters(self, survivor_id: str, other_id: str):
        """
        Merge other_id into survivor_id. Mirrors Cluster.merge() in Code 1:
            new_centroid = (centroid_a * na + centroid_b * nb) / (na + nb)
            centroid_time = weighted average of both centroid times
        """
        meta_a    = json.loads(self.cluster_meta.get(survivor_id))
        meta_b    = json.loads(self.cluster_meta.get(other_id))
        cent_a    = np.array(json.loads(self.cluster_centroids.get(survivor_id)), dtype=np.float32)
        cent_b    = np.array(json.loads(self.cluster_centroids.get(other_id)),    dtype=np.float32)

        na, nb    = meta_a["member_count"], meta_b["member_count"]

        new_centroid = (cent_a * na + cent_b * nb) / (na + nb)
        norm         = np.linalg.norm(new_centroid)
        new_centroid = new_centroid / (norm + 1e-9)

        ts_a = float(meta_a["centroid_time"])
        ts_b = float(meta_b["centroid_time"])
        new_ct = (ts_a * na + ts_b * nb) / (na + nb)

        merged_meta = {
            "member_count" : na + nb,
            "centroid_time": new_ct,
            "last_updated" : max(meta_a["last_updated"], meta_b["last_updated"]),
        }

        self.cluster_meta.put(survivor_id, json.dumps(merged_meta))
        self.cluster_centroids.put(survivor_id, json.dumps(new_centroid.tolist()))

        # Remove the absorbed cluster
        self.cluster_meta.remove(other_id)
        self.cluster_centroids.remove(other_id)

    # ── Noise helpers ─────────────────────────────────────────────────────────

    def _add_to_noise(self, vec: np.ndarray, event: dict, noise_list: list):
        """
        Serialise a (vec, event) pair and append to noise_buffer state.
        """
        item = json.dumps({"vec": vec.tolist(), "event": event})
        self.noise_buffer.add(item)

    def _recheck_noise(self, noise_list: list) -> list:
        """
        Noise points that now fall within EPSILON of a real cluster join it.
        Mirrors CentroidClusterer._recheck_noise() in Code 1.
        Returns the updated noise list (items that remain noise).
        """
        still_noise = []
        for raw in noise_list:
            item     = json.loads(raw)
            nvec     = np.array(item["vec"], dtype=np.float32)
            nevent   = item["event"]
            event_ts = parse_ts(nevent["received_at"])

            close = self._find_close_clusters(nvec, event_ts)
            if close:
                survivor = str(min(int(c) for c in close))
                self._update_cluster(survivor, nvec, event_ts)
            else:
                still_noise.append(raw)
        return still_noise

    def _promote_noise(self, noise_list: list) -> list:
        """
        If MIN_PTS noise points are mutually within EPSILON, they form a new cluster.
        Mirrors CentroidClusterer._promote_noise() in Code 1.
        Returns updated noise list with promoted items removed.
        """
        if len(noise_list) < MIN_PTS:
            return noise_list

        items = [json.loads(r) for r in noise_list]
        vecs  = [np.array(it["vec"],   dtype=np.float32) for it in items]
        tss   = [parse_ts(it["event"]["received_at"])     for it in items]

        used = set()
        for i in range(len(items)):
            if i in used:
                continue
            neighbours = [
                j for j in range(len(items))
                if j != i and j not in used
                and penalised_distance(vecs[i], vecs[j], tss[i], tss[j]) < EPSILON
            ]
            if len(neighbours) >= MIN_PTS - 1:
                seed_indices = [i] + neighbours
                # Create a new cluster seeded by item i
                cid = self._create_cluster(vecs[i], items[i]["event"], tss[i])
                # Add all neighbours into the new cluster
                for idx in neighbours:
                    self._update_cluster(cid, vecs[idx], tss[idx])
                used.update(seed_indices)

        return [noise_list[idx] for idx in range(len(noise_list)) if idx not in used]

    # ── Cassandra flush (placeholder) ─────────────────────────────────────────

    def _flush_cluster_to_cassandra(self, cluster_id: str, meta: dict):
        """
        Write a settled cluster to Cassandra for long-term storage.
        Replace this with your actual Cassandra driver call.
        """
        pass


# ─── Flink Job Entry Point ────────────────────────────────────────────────────

def build_pipeline(env: StreamExecutionEnvironment, input_stream):
    """
    Wire up the clustering operator into a Flink pipeline.

    input_stream: DataStream of dicts matching CanonicalEvent schema
                  (event_id, platform, received_at, sender, event_type,
                   description, content)

    Output: same dicts enriched with "assigned_to" (int cluster id, or -1 for noise)
    """
    return (
        input_stream
        .key_by(lambda e: e["sender"]["id"])   # partition by user — mirrors Code 1's per-user state
        .process(ClusteringProcessFunction())
    )


if __name__ == "__main__":
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    # Ensure the Kafka SQL Connector JAR is available.
    # Download it from: https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.0.0-1.17/flink-sql-connector-kafka-3.0.0-1.17.jar
    # env.add_jars("file:///path/to/flink-sql-connector-kafka-3.0.0-1.17.jar")

    # 1. Define source: Read from 'input_events' topic
    source = KafkaSource.builder() \
        .set_bootstrap_servers("kafka-1:29092,kafka-2:29092,kafka-3:29092") \
        .set_topics("input_events") \
        .set_group_id("clustering_group") \
        .set_starting_offsets(OffsetsInitializer.earliest()) \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

    # 2. Define sink: Write to 'clustered_events' topic
    sink = KafkaSink.builder() \
        .set_bootstrap_servers("kafka-1:29092,kafka-2:29092,kafka-3:29092") \
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic("clustered_events")
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        ) \
        .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE) \
        .build()

    # 3. Build & Execute Pipeline
    # Read string from Kafka -> Parse JSON -> Cluster -> Serialize JSON -> Write to Kafka
    stream = env.from_source(source, WatermarkStrategy.no_watermarks(), "Kafka Source")
    
    processed_stream = (
        stream
        .map(lambda x: json.loads(x))  # Deserialize JSON string
        .key_by(lambda e: e["sender"]["id"])
        .process(ClusteringProcessFunction())
        .map(lambda x: json.dumps(x))  # Serialize result to JSON string
    )

    processed_stream.sink_to(sink)

    env.execute("centroid_clustering_job")