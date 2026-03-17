# syntax=docker/dockerfile:1

FROM eclipse-temurin:21-jre
WORKDIR /app

COPY build/*-runner.jar /app/inf-javabatch-app.jar

ENTRYPOINT ["java", "-jar", "/app/inf-javabatch-app.jar"]
CMD ["--help"]
