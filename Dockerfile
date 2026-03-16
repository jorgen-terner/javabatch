FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY batch_poc /app/batch_poc
COPY inf_batch_job_app.py /app/inf_batch_job_app.py
COPY example_javabatch.py /app/example_javabatch.py

ENTRYPOINT ["python", "/app/inf_batch_job_app.py"]
