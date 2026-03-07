package com.chatters.flink;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.apache.flink.api.common.functions.RichMapFunction;
import org.apache.http.client.methods.CloseableHttpResponse;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.util.EntityUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Map function that calls Python clustering service via HTTP
 */
public class ClusteringMapFunction extends RichMapFunction<String, String> {
    
    private static final Logger LOG = LoggerFactory.getLogger(ClusteringMapFunction.class);
    
    private final String pythonServiceUrl;
    private transient CloseableHttpClient httpClient;
    private transient ObjectMapper objectMapper;
    
    public ClusteringMapFunction(String pythonServiceUrl) {
        this.pythonServiceUrl = pythonServiceUrl;
    }
    
    @Override
    public void open(org.apache.flink.configuration.Configuration parameters) {
        this.httpClient = HttpClients.createDefault();
        this.objectMapper = new ObjectMapper();
        LOG.info("Initialized ClusteringMapFunction with service URL: {}", pythonServiceUrl);
    }
    
    @Override
    public String map(String eventJson) throws Exception {
        try {
            // Parse input JSON
            JsonNode eventNode = objectMapper.readTree(eventJson);
            
            // Extract required fields for clustering
            String userId = eventNode.has("sender") && eventNode.get("sender").has("id")
                ? eventNode.get("sender").get("id").asText()
                : "unknown";
            
            String description = eventNode.has("description")
                ? eventNode.get("description").asText()
                : "";
            
            String receivedAt = eventNode.has("received_at")
                ? eventNode.get("received_at").asText()
                : String.valueOf(System.currentTimeMillis() / 1000);
            
            // Prepare request payload for Python service
            ObjectNode requestPayload = objectMapper.createObjectNode();
            requestPayload.put("user_id", userId);
            requestPayload.put("description", description);
            requestPayload.put("received_at", receivedAt);
            
            // Call Python clustering service
            HttpPost request = new HttpPost(pythonServiceUrl);
            request.setHeader("Content-Type", "application/json");
            request.setEntity(new StringEntity(requestPayload.toString()));
            
            try (CloseableHttpResponse response = httpClient.execute(request)) {
                int statusCode = response.getStatusLine().getStatusCode();
                String responseBody = EntityUtils.toString(response.getEntity());
                
                if (statusCode == 200) {
                    // Parse response
                    JsonNode responseNode = objectMapper.readTree(responseBody);
                    int assignedTo = responseNode.has("assigned_to")
                        ? responseNode.get("assigned_to").asInt()
                        : -1;
                    
                    // Add cluster assignment to original event
                    ((ObjectNode) eventNode).put("assigned_to", assignedTo);
                    
                    LOG.debug("Event clustered: user={}, cluster={}", userId, assignedTo);
                } else {
                    LOG.warn("Clustering service returned status {}: {}", statusCode, responseBody);
                    ((ObjectNode) eventNode).put("assigned_to", -1);
                    ((ObjectNode) eventNode).put("clustering_error", "Service returned " + statusCode);
                }
            }
            
            return objectMapper.writeValueAsString(eventNode);
            
        } catch (Exception e) {
            LOG.error("Error processing event: {}", e.getMessage(), e);
            
            // Return original event with error marker
            try {
                JsonNode eventNode = objectMapper.readTree(eventJson);
                ((ObjectNode) eventNode).put("assigned_to", -1);
                ((ObjectNode) eventNode).put("clustering_error", e.getMessage());
                return objectMapper.writeValueAsString(eventNode);
            } catch (Exception parseError) {
                // If we can't even parse, return a minimal error response
                ObjectNode errorNode = objectMapper.createObjectNode();
                errorNode.put("assigned_to", -1);
                errorNode.put("error", "Failed to process event");
                errorNode.put("original_event", eventJson);
                return objectMapper.writeValueAsString(errorNode);
            }
        }
    }
    
    @Override
    public void close() {
        try {
            if (httpClient != null) {
                httpClient.close();
            }
        } catch (Exception e) {
            LOG.error("Error closing HTTP client", e);
        }
    }
}
