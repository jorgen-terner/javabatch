package com.example.infjavabatch;

import io.quarkus.runtime.Quarkus;
import io.quarkus.runtime.QuarkusApplication;
import io.quarkus.runtime.annotations.QuarkusMain;
import jakarta.inject.Inject;

@QuarkusMain
public class InfJavaBatchMain implements QuarkusApplication {

    @Inject
    JavabatchClientService javabatchClientService;

    @Inject
    MonitorService monitorService;

    public static void main(String... args) {
        Quarkus.run(InfJavaBatchMain.class, args);
    }

    @Override
    public int run(String... args) {
        int exitCode = javabatchClientService.run(args, monitorService);
        Quarkus.asyncExit(exitCode);
        return exitCode;
    }
}
