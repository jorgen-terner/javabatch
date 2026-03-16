# javabatch batch-poc integration

Denna katalog innehaller en referensimplementation av inf-batch-job-app med:

- restartJob i BatchJobService-granssnittet
- BATCH_TYP-styrd metricsrapportering
- JAVABATCH-mappning som ersatter monitor-skriptet i example_monitor.py

## BATCH_TYP-regel

- Om BATCH_TYP=JAVABATCH: rapportera metrics enligt example_monitor.py-logik.
- Annars: ingen metricsrapportering (Noop).

## Bygg image

```powershell
docker build -t inf-batch-job-app:latest .
```

Bygg script-image for example_javabatch.py:

```powershell
docker build -f Dockerfile.javabatch-script -t javabatch-script:latest .
```

## Kor lokalt

```powershell
python inf_batch_job_app.py --job-config .\examplejob.ini --action restart --job-args "myJob=true" --configmap-name inf-batch-job-config
```

## Kubernetes

1. Skapa configmap for batchtyp:

```powershell
kubectl apply -f k8s/inf-batch-job-configmap.yaml
```

2. Ge batch-poc rattigheter att skapa child Jobs:

```powershell
kubectl apply -f k8s/batch-poc-job-dispatcher-rbac.yaml
```

3. Skapa dispatch-Job (batch-poc skapar separat script-Job):

```powershell
kubectl apply -f k8s/javabatch-dispatcher-job.yaml
```

4. Alternativt skapa Job direkt utan dispatch:

```powershell
kubectl apply -f k8s/javabatch-job.yaml
```

## Dispatch via CLI

Exempel pa action som skapar ett separat script-Job:

```powershell
python inf_batch_job_app.py --job-config .\examplejob.ini --action dispatch-script-job --script-image your-registry/javabatch-script:latest --script-action restart --job-args "myJob=true" --configmap-name inf-batch-job-config
```
