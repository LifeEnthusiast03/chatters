package com.chatters.flink;

import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Flink Streaming Job for Message Clustering
 * Reads from Kafka, calls Python clustering service, writes back to Kafka
 */
public class ClusteringJob {
    
    private static final Logger LOG = LoggerFactory.getLogger(ClusteringJob.class);
    
    private static final String KAFKA_BROKERS = "localhost:9092";
    private static final String INPUT_TOPIC = "sanitized-event";
    private static final String OUTPUT_TOPIC = "clustered_events";
    private static final String CONSUMER_GROUP = "clustering_group";
    private static final String PYTHON_SERVICE_URL = "http://localhost:5000/cluster";
    
    public static void main(String[] args) throws Exception {
        
        // Set up the streaming execution environment
        final StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        
        // Set parallelism
        env.setParallelism(1);
        
        // Create Kafka source
        KafkaSource<String> source = KafkaSource.<String>builder()
            .setBootstrapServers(KAFKA_BROKERS)
            .setTopics(INPUT_TOPIC)
            .setGroupId(CONSUMER_GROUP)
            .setStartingOffsets(OffsetsInitializer.earliest())
            .setValueOnlyDeserializer(new SimpleStringSchema())
            .build();
        
        // Create Kafka sink
        KafkaSink<String> sink = KafkaSink.<String>builder()
            .setBootstrapServers(KAFKA_BROKERS)
            .setRecordSerializer(
                KafkaRecordSerializationSchema.builder()
                    .setTopic(OUTPUT_TOPIC)
                    .setValueSerializationSchema(new SimpleStringSchema())
                    .build()
            )
            .build();
        
        // Build processing pipeline
        DataStream<String> inputStream = env.fromSource(
            source,
            WatermarkStrategy.noWatermarks(),
            "Kafka Source"
        );
        
        // Process events through clustering service
        DataStream<String> clusteredStream = inputStream
            .map(new ClusteringMapFunction(PYTHON_SERVICE_URL))
            .name("Clustering Processor");
        
        // Write to output topic
        clusteredStream.sinkTo(sink).name("Kafka Sink");
        
        // Execute the job
        LOG.info("Starting Flink Clustering Job...");
        LOG.info("Reading from: {}", INPUT_TOPIC);
        LOG.info("Writing to: {}", OUTPUT_TOPIC);
        LOG.info("Python service: {}", PYTHON_SERVICE_URL);
        
        env.execute("Message Clustering Job");
    }
}
