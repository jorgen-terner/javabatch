package com.example.infjavabatch;

import jakarta.enterprise.context.ApplicationScoped;

import java.net.InetAddress;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Optional;

@ApplicationScoped
public class MonitorService {

    private static final DateTimeFormatter START_TIME_FORMAT =
        DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss").withZone(ZoneId.systemDefault());

    private final HttpClient httpClient = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(5))
        .build();

    public void report(String state, long pid, Instant processStart) {
        try {
            String server = shortHostname();
            MetricsTarget target = resolveTarget(server);
            String environment = "jbatch";

            String object = sanitizeObject(System.getenv("TO_JOB_NAME"));
            if (object.isBlank()) {
                object = "javabatch";
            }

            String chart = Optional.ofNullable(System.getenv("TO_ENV_NAME"))
                .filter(v -> !v.isBlank())
                .orElse("MANUELL");

            String user = Optional.ofNullable(System.getenv("LOGNAME"))
                .orElse(Optional.ofNullable(System.getenv("USERNAME")).orElse("unknown"));

            String objectStatus;
            int statusFlag;
            String influxDb;

            switch (state) {
                case "start":
                    objectStatus = "Executing";
                    statusFlag = 0;
                    influxDb = target.execDb();
                    break;
                case "stop":
                    objectStatus = "Completed";
                    statusFlag = 2;
                    influxDb = target.historyDb();
                    break;
                default:
                    objectStatus = "Failed";
                    statusFlag = 1;
                    influxDb = target.historyDb();
                    break;
            }

            dropSeries(target.metricHost(), target.execDb(), object);
            writeStatus(
                target.metricHost(),
                influxDb,
                object,
                objectStatus,
                pid,
                user,
                server,
                chart,
                environment,
                processStart,
                statusFlag
            );
        } catch (Exception e) {
            System.out.println("Monitor reporting failed, continuing: " + e.getMessage());
        }
    }

    private void dropSeries(String metricHost, String dbName, String object) throws Exception {
        String query = "DROP SERIES from exec_job where JOB='" + object + "'";
        String body = "q=" + URLEncoder.encode(query, StandardCharsets.UTF_8);

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create("http://" + metricHost + ".sfa.se:8086/query?db=" + dbName))
            .header("Content-Type", "application/x-www-form-urlencoded")
            .timeout(Duration.ofSeconds(10))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .build();

        httpClient.send(request, HttpResponse.BodyHandlers.discarding());
    }

    private void writeStatus(
        String metricHost,
        String dbName,
        String object,
        String objectStatus,
        long pid,
        String user,
        String server,
        String chart,
        String environment,
        Instant processStart,
        int statusFlag
    ) throws Exception {
        String startTime = START_TIME_FORMAT.format(processStart);
        String elapsed = formatElapsed(processStart, Instant.now());

        String line = "exec_job,JOB=" + object + " "
            + "Object=\"" + escapeValue(object) + "\","
            + "Start_time=\"" + escapeValue(startTime) + "\","
            + "Status=\"" + escapeValue(objectStatus) + "\","
            + "PID=" + pid + ","
            + "User=\"" + escapeValue(user) + "\","
            + "Server=\"" + escapeValue(server) + "\","
            + "Chart=\"" + escapeValue(chart) + "\","
            + "Environment=\"" + escapeValue(environment) + "\","
            + "Elapsed=\"" + escapeValue(elapsed) + "\","
            + "Status_flag=" + statusFlag;

        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create("http://" + metricHost + ".sfa.se:8086/write?db=" + dbName))
            .header("Content-Type", "text/plain; charset=utf-8")
            .timeout(Duration.ofSeconds(10))
            .POST(HttpRequest.BodyPublishers.ofString(line))
            .build();

        httpClient.send(request, HttpResponse.BodyHandlers.discarding());
    }

    private String shortHostname() {
        try {
            String hostname = InetAddress.getLocalHost().getHostName();
            int dotIdx = hostname.indexOf('.');
            return dotIdx > 0 ? hostname.substring(0, dotIdx) : hostname;
        } catch (Exception e) {
            return "unknown";
        }
    }

    private MetricsTarget resolveTarget(String server) {
        if (server.contains("prod")) {
            return new MetricsTarget("fkmetrics", "surv_executing", "surv_history");
        }
        return new MetricsTarget("metricstest", "davve", "davve");
    }

    private String sanitizeObject(String input) {
        if (input == null) {
            return "";
        }
        return input.replaceAll("[^a-zA-Z0-9,_-]", "");
    }

    private String formatElapsed(Instant start, Instant end) {
        long seconds = Math.max(0, Duration.between(start, end).getSeconds());
        long hours = seconds / 3600;
        long minutes = (seconds % 3600) / 60;
        long remainingSeconds = seconds % 60;
        return String.format("%02d:%02d:%02d", hours, minutes, remainingSeconds);
    }

    private String escapeValue(String value) {
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private record MetricsTarget(String metricHost, String execDb, String historyDb) {
    }
}
