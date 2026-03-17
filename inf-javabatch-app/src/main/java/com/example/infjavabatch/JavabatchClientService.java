package com.example.infjavabatch;

import jakarta.enterprise.context.ApplicationScoped;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

@ApplicationScoped
public class JavabatchClientService {

    private final HttpClient httpClient = HttpClient.newHttpClient();

    public int run(String[] args, MonitorService monitorService) {
        CliOptions options = CliOptions.parse(args);

        if (options.showHelp || options.action == Action.NONE) {
            printHelp();
            return options.showHelp ? 0 : 2;
        }

        if (options.jobFile == null || options.jobFile.isBlank()) {
            printHelp();
            return 2;
        }

        EndpointConfig endpoints;
        try {
            endpoints = parseEndpointConfig(Path.of(options.jobFile));
        } catch (IOException e) {
            System.out.println("Could not read job file: " + e.getMessage());
            return 1;
        }

        long pid = ProcessHandle.current().pid();
        Instant processStart = Instant.now();
        System.out.println("PID=" + pid);

        final boolean[] completed = {false};
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            if (!completed[0]) {
                monitorService.report("error", pid, processStart);
            }
        }));

        try {
            int result;
            if (options.action == Action.START) {
                System.out.println("starting job");
                monitorService.report("start", pid, processStart);
                result = startJob(endpoints, options.jobArgs, options.token, monitorService, pid, processStart);
            } else if (options.action == Action.STOP) {
                System.out.println("stopping job");
                monitorService.report("start", pid, processStart);
                result = stopJob(endpoints.stop(), options.jobArgs, options.token, monitorService, pid, processStart);
            } else if (options.action == Action.STATUS) {
                System.out.println("checking status on job");
                monitorService.report("start", pid, processStart);
                result = jobStatus(endpoints.status(), options.jobArgs, options.token, monitorService, pid, processStart);
            } else if (options.action == Action.RESTART) {
                System.out.println("restarting job");
                monitorService.report("start", pid, processStart);
                result = restartJob(endpoints.restart(), options.jobArgs, options.token, monitorService, pid, processStart);
            } else if (options.action == Action.SUMMARY) {
                System.out.println("summary on job");
                result = summaryJob(options.jobArgs, endpoints.summary(), options.token);
            } else if (options.action == Action.HELP) {
                System.out.println("Printing help");
                result = helpEndpoint(endpoints.help(), options.token);
            } else {
                result = 2;
            }

            completed[0] = true;
            return result;
        } catch (Exception e) {
            System.out.println(e.getMessage());
            monitorService.report("error", pid, processStart);
            return 1;
        }
    }

    private int startJob(
        EndpointConfig endpoints,
        String jobArgs,
        String token,
        MonitorService monitorService,
        long pid,
        Instant processStart
    ) throws Exception {
        ensureEndpoint(endpoints.start(), "start");
        ensureEndpoint(endpoints.status(), "status");
        ensureEndpoint(endpoints.summary(), "summary");

        String url = endpoints.start() + "/" + value(jobArgs);
        System.out.println(url);

        HttpResponse<String> response = sendGet(url, token);
        if (is2xx(response.statusCode())) {
            String execId = response.body();
            System.out.println("executionId: " + execId);
            callOpsCmd(execId);
            return startJobStatus(execId, endpoints.status(), endpoints.summary(), token, monitorService, pid, processStart);
        }

        System.out.println(response.body());
        monitorService.report("error", pid, processStart);
        return 1;
    }

    private int startJobStatus(
        String execId,
        String pathStatus,
        String pathSummary,
        String token,
        MonitorService monitorService,
        long pid,
        Instant processStart
    ) throws Exception {
        String url = pathStatus + "/" + execId;
        int fault = 0;
        System.out.println(url);

        while (true) {
            Thread.sleep(5000);
            HttpResponse<String> response = sendGet(url, token);

            if (is2xx(response.statusCode())) {
                String statusText = response.body();
                if (statusText.contains("COMPLETED")) {
                    System.out.println(statusText);
                    summaryJob(execId, pathSummary, token);
                    monitorService.report("stop", pid, processStart);
                    return 0;
                }
                if (statusText.contains("STARTED")) {
                    System.out.println("Running...");
                    continue;
                }
                if (statusText.contains("STARTING")) {
                    continue;
                }

                System.out.println(statusText);
                monitorService.report("error", pid, processStart);
                return 1;
            }

            System.out.println(response.body());
            if (fault == 5) {
                monitorService.report("error", pid, processStart);
                return 1;
            }
            fault++;
        }
    }

    private int jobStatus(
        String pathStatus,
        String execId,
        String token,
        MonitorService monitorService,
        long pid,
        Instant processStart
    ) throws Exception {
        ensureEndpoint(pathStatus, "status");
        String url = pathStatus + "/" + value(execId);
        System.out.println(url);

        HttpResponse<String> response = sendGet(url, token);
        System.out.println(response.body());
        monitorService.report("stop", pid, processStart);
        return is2xx(response.statusCode()) ? 0 : 1;
    }

    private int summaryJob(String execId, String pathSummary, String token) throws Exception {
        ensureEndpoint(pathSummary, "summary");
        String url = pathSummary + "/" + value(execId);
        System.out.println(url);

        HttpResponse<String> response = sendGet(url, token);
        System.out.println(response.body());
        return is2xx(response.statusCode()) ? 0 : 1;
    }

    private int stopJob(
        String pathStop,
        String jobArgs,
        String token,
        MonitorService monitorService,
        long pid,
        Instant processStart
    ) throws Exception {
        ensureEndpoint(pathStop, "stop");
        String url = pathStop + "/" + value(jobArgs);
        System.out.println(url);

        HttpResponse<String> response = sendGet(url, token);
        System.out.println(response.body());
        if (is2xx(response.statusCode())) {
            monitorService.report("stop", pid, processStart);
            return 0;
        }

        monitorService.report("error", pid, processStart);
        return 1;
    }

    private int restartJob(
        String pathRestart,
        String jobArgs,
        String token,
        MonitorService monitorService,
        long pid,
        Instant processStart
    ) throws Exception {
        ensureEndpoint(pathRestart, "restart");
        String url = pathRestart + "/" + value(jobArgs);
        System.out.println(url);

        HttpResponse<String> response = sendGet(url, token);
        if (is2xx(response.statusCode())) {
            System.out.println("executionId: " + response.body());
            return 0;
        }

        System.out.println(response.body());
        monitorService.report("error", pid, processStart);
        return 1;
    }

    private int helpEndpoint(String pathHelp, String token) throws Exception {
        ensureEndpoint(pathHelp, "help");
        System.out.println(pathHelp);
        HttpResponse<String> response = sendGet(pathHelp, token);
        System.out.println(response.body());
        return is2xx(response.statusCode()) ? 0 : 1;
    }

    private HttpResponse<String> sendGet(String url, String token) throws Exception {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(url))
            .header("Content-Type", "application/json; charset=utf-8")
            .header("FKST", value(token))
            .GET()
            .build();
        return httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
    }

    private EndpointConfig parseEndpointConfig(Path path) throws IOException {
        Map<String, String> endpoints = new HashMap<>();
        boolean inEndpoints = false;

        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String line;
            while ((line = reader.readLine()) != null) {
                String trimmed = line.trim();
                if (trimmed.isEmpty() || trimmed.startsWith("#") || trimmed.startsWith(";")) {
                    continue;
                }
                if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
                    inEndpoints = "[endpoints]".equalsIgnoreCase(trimmed);
                    continue;
                }
                if (!inEndpoints) {
                    continue;
                }

                int idx = trimmed.indexOf('=');
                if (idx <= 0) {
                    continue;
                }

                String key = trimmed.substring(0, idx).trim();
                String value = trimmed.substring(idx + 1).trim();
                endpoints.put(key, value);
            }
        }

        return new EndpointConfig(
            endpoints.get("springbatchpy.v2.start"),
            endpoints.get("springbatchpy.v2.status"),
            endpoints.get("springbatchpy.v2.stop"),
            endpoints.get("springbatchpy.v2.restart"),
            endpoints.get("springbatchpy.v2.summary"),
            endpoints.get("springbatchpy.v2.help")
        );
    }

    private void callOpsCmd(String executionId) {
        try {
            Process process = new ProcessBuilder(
                "/openprocess/Automator/PServer/bin/opscmd",
                "resval",
                "-res",
                "executionId",
                "-value",
                executionId
            ).inheritIO().start();
            process.waitFor();
        } catch (Exception e) {
            System.out.println("OP chart parameter executionId not updated, continuing");
        }
    }

    private void ensureEndpoint(String endpoint, String key) {
        if (endpoint == null || endpoint.isBlank()) {
            throw new IllegalArgumentException("Missing endpoint config for " + key);
        }
    }

    private boolean is2xx(int statusCode) {
        return statusCode >= 200 && statusCode < 300;
    }

    private String value(String value) {
        return Optional.ofNullable(value).orElse("");
    }

    private void printHelp() {
        System.out.println("Script som startar ett batchjobb. Argument som krävs finns beskrivna nedan.");
        System.out.println("Mer information går att hitta på https://confluence.sfa.se/display/SOHDLS/Script\n");
        System.out.println("Exempel: java -jar inf-javabatch-app-runner.jar -j examplejob.ini --start\n");
        System.out.println("Tvingande argument:");
        System.out.println("-j eller --job                                      (ini-fil med endpoints)");
        System.out.println("");
        System.out.println(" --start, --status, --restart, --stop eller --help  (Endast en av dessa krävs)");
        System.out.println("");
        System.out.println("Frivillga argument:");
        System.out.println("-a eller --jobargs                               (argument som tjänsten tar emot, i formatet \"key=value\")");
        System.out.println("-t eller --token                                 (FKST token)");
        System.out.println("--summary");
    }

    private enum Action {
        NONE,
        START,
        STATUS,
        STOP,
        RESTART,
        SUMMARY,
        HELP
    }

    private static final class CliOptions {
        private String jobFile;
        private String jobArgs = "";
        private String token = "";
        private Action action = Action.NONE;
        private boolean showHelp;

        private static CliOptions parse(String[] args) {
            CliOptions options = new CliOptions();
            for (int i = 0; i < args.length; i++) {
                String arg = args[i];

                switch (arg) {
                    case "-h":
                        options.showHelp = true;
                        break;
                    case "-j":
                    case "--job":
                        options.jobFile = nextValue(args, ++i, arg);
                        break;
                    case "-a":
                    case "--jobargs":
                        options.jobArgs = nextValue(args, ++i, arg);
                        break;
                    case "-t":
                    case "--token":
                        options.token = nextValue(args, ++i, arg);
                        break;
                    case "--start":
                        options.action = Action.START;
                        break;
                    case "--status":
                        options.action = Action.STATUS;
                        break;
                    case "--stop":
                        options.action = Action.STOP;
                        break;
                    case "--restart":
                        options.action = Action.RESTART;
                        break;
                    case "--summary":
                        options.action = Action.SUMMARY;
                        break;
                    case "--help":
                        options.action = Action.HELP;
                        break;
                    default:
                        throw new IllegalArgumentException("Unknown argument: " + arg);
                }
            }
            return options;
        }

        private static String nextValue(String[] args, int index, String option) {
            if (index >= args.length) {
                throw new IllegalArgumentException("Missing value for " + option);
            }
            return Objects.requireNonNullElse(args[index], "");
        }
    }
}
