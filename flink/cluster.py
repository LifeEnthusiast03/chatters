from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.functions import KeyedProcessFunction, RuntimeContext
from pyflink.datastream.state import ValueStateDescriptor, ListStateDescriptor, MapStateDescriptor
from pyflink.common.typeinfo import Types
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.watermark_strategy import WatermarkStrategy

from pyflink.datastream.connectors.kafka import (
    KafkaSource,
    KafkaSink,
    KafkaRecordSerializationSchema,
    DeliveryGuarantee,
    KafkaOffsetsInitializer
)

import json
import numpy as np
import math
from datetime import datetime


EPSILON = 0.56
MIN_PTS = 1
LAMBDA_TIME = 0.35
TAU_SECONDS = 86400.0


def cosine_distance(vec_a, vec_b):
    dot = float(np.dot(vec_a, vec_b))
    dot = max(-1.0, min(1.0, dot))
    return 1.0 - dot


def time_penalty(ts_a, ts_b):
    delta_seconds = abs(ts_a - ts_b)
    return LAMBDA_TIME * (1.0 - math.exp(-delta_seconds / TAU_SECONDS))


def penalised_distance(vec_a, vec_b, ts_a, ts_b):
    return cosine_distance(vec_a, vec_b) + time_penalty(ts_a, ts_b)


def embed_and_normalise(embedder, description):
    vec = embedder.encode([description], show_progress_bar=False)[0]
    norm = np.linalg.norm(vec)
    return (vec / (norm + 1e-9)).astype(np.float32)


def parse_ts(received_at):
    if isinstance(received_at, (int, float)):
        return float(received_at)
    return datetime.fromisoformat(str(received_at)).timestamp()


class ClusteringProcessFunction(KeyedProcessFunction):

    def open(self, runtime_context: RuntimeContext):

        self.cluster_meta = runtime_context.get_map_state(
            MapStateDescriptor("cluster_meta", Types.STRING(), Types.STRING())
        )

        self.cluster_centroids = runtime_context.get_map_state(
            MapStateDescriptor("cluster_centroids", Types.STRING(), Types.STRING())
        )

        self.noise_buffer = runtime_context.get_list_state(
            ListStateDescriptor("noise_buffer", Types.STRING())
        )

        self.next_cluster_id = runtime_context.get_state(
            ValueStateDescriptor("next_cluster_id", Types.INT())
        )

        from sentence_transformers import SentenceTransformer
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")

    def process_element(self, event, ctx):

        description = event.get("description", "")
        received_at = event.get("received_at")
        event_ts = parse_ts(received_at)

        vec = embed_and_normalise(self.embedder, description)

        noise_list = list(self.noise_buffer.get() or [])

        has_clusters = any(True for _ in self.cluster_meta.keys())
        has_noise = len(noise_list) > 0

        if not has_clusters and not has_noise:
            self._add_to_noise(vec, event)
            yield {**event, "assigned_to": -1}
            return

        close_ids = self._find_close_clusters(vec, event_ts)

        if len(close_ids) == 0:
            self._add_to_noise(vec, event)
            assigned = -1

        else:
            cid = close_ids[0]
            self._update_cluster(cid, vec, event_ts)
            assigned = int(cid)

        yield {**event, "assigned_to": assigned}

    def _get_next_id(self):
        current = self.next_cluster_id.value()
        nid = 0 if current is None else current
        self.next_cluster_id.update(nid + 1)
        return str(nid)

    def _find_close_clusters(self, vec, event_ts):

        close = []

        for cluster_id in self.cluster_meta.keys():

            centroid = np.array(
                json.loads(self.cluster_centroids.get(cluster_id)),
                dtype=np.float32
            )

            meta = json.loads(self.cluster_meta.get(cluster_id))

            centroid_ts = float(meta["centroid_time"])

            dist = penalised_distance(vec, centroid, event_ts, centroid_ts)

            if dist < EPSILON:
                close.append(cluster_id)

        return close

    def _create_cluster(self, vec, event_ts):

        cid = self._get_next_id()

        meta = {
            "member_count": 1,
            "centroid_time": event_ts,
            "last_updated": event_ts,
        }

        self.cluster_meta.put(cid, json.dumps(meta))
        self.cluster_centroids.put(cid, json.dumps(vec.tolist()))

        return cid

    def _update_cluster(self, cluster_id, new_vec, event_ts):

        meta = json.loads(self.cluster_meta.get(cluster_id))

        centroid = np.array(
            json.loads(self.cluster_centroids.get(cluster_id)),
            dtype=np.float32
        )

        n = meta["member_count"]

        new_centroid = (centroid * n + new_vec) / (n + 1)

        norm = np.linalg.norm(new_centroid)

        new_centroid = new_centroid / (norm + 1e-9)

        meta["member_count"] = n + 1
        meta["centroid_time"] = event_ts
        meta["last_updated"] = event_ts

        self.cluster_meta.put(cluster_id, json.dumps(meta))
        self.cluster_centroids.put(cluster_id, json.dumps(new_centroid.tolist()))

    def _add_to_noise(self, vec, event):

        item = json.dumps({"vec": vec.tolist(), "event": event})

        self.noise_buffer.add(item)


def build_pipeline(env, input_stream):

    return (
        input_stream
        .key_by(lambda e: e["user_id"])
        .process(ClusteringProcessFunction())
    )


if __name__ == "__main__":

    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    source = KafkaSource.builder() \
        .set_bootstrap_servers("localhost:9092") \
        .set_topics("sanitized-event") \
        .set_group_id("clustering_group") \
        .set_starting_offsets(KafkaOffsetsInitializer.earliest()) \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

    sink = KafkaSink.builder() \
        .set_bootstrap_servers("localhost:9092") \
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic("clustered_events")
            .set_value_serialization_schema(SimpleStringSchema())
            .build()
        ) \
        .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE) \
        .build()

    stream = env.from_source(
        source,
        WatermarkStrategy.no_watermarks(),
        "Kafka Source"
    )

    processed_stream = (
        stream
        .map(lambda x: json.loads(x), output_type=Types.MAP(Types.STRING(), Types.STRING()))
        .key_by(lambda e: e["user_id"])
        .process(ClusteringProcessFunction())
        .map(lambda x: json.dumps(x), output_type=Types.STRING())
    )

    processed_stream.sink_to(sink)

    env.execute("centroid_clustering_job")