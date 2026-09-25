FROM eclipse-temurin:25-jre@sha256:bb036ed6cfdc57e3da7c22634d15f1b840d2caf76183861c80e81ca4b5104abb
WORKDIR /engine
COPY batfish.jar ./batfish.jar
COPY questions ./questions
COPY provenance.json ./provenance.json
COPY --chmod=0555 engine-health.sh ./health.sh
USER 10001:10001
ENTRYPOINT ["java", "-Xms256m", "-Xmx4g", "-jar", "/engine/batfish.jar", "-runclient", "false", "-loglevel", "error", "-coordinatorargs", "-workbindhost 0.0.0.0 -workv2port 9996 -containerslocation /data/containers -templatedirs /engine/questions"]
