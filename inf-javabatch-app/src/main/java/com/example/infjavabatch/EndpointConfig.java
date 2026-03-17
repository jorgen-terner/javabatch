package com.example.infjavabatch;

public record EndpointConfig(
    String start,
    String status,
    String stop,
    String restart,
    String summary,
    String help
) {
}
