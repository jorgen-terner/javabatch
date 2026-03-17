# inf-javabatch-app

Quarkus-baserad migrering av:
- `../javabatch.py`
- `../monitor_jbatch.sh`

Applikationen ar en CLI-process (inte REST) och mirrorar huvudsakliga kommandon: `--start`, `--status`, `--stop`, `--restart`, `--summary`, `--help`.

## Gradle

Projektet ar satt upp med samma Gradle-wrapperversion som i `batch-poc`: `9.0`.

## Bygg

```powershell
cd c:\repos\javabatch-v2\inf-javabatch-app
gradle build
```

Om wrapper scripts finns, anvand i stallet:

```powershell
.\gradlew.bat build
```

## Korning

```powershell
java -jar build\quarkus-app\quarkus-run.jar -j c:\repos\javabatch-v2\examplejob.ini --start -a "myJob=true" -t "<token>"
```

## Monitorering (migrerad fran monitor_jbatch.sh)

Monitorering skickas till Influx med samma state-mappning:
- `start` -> `Executing` + `Status_flag=0`
- `error` -> `Failed` + `Status_flag=1`
- `stop` -> `Completed` + `Status_flag=2`

Miljovariabler som stods:
- `TO_JOB_NAME`
- `TO_ENV_NAME`
- `LOGNAME` / `USERNAME`
