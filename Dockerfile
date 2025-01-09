FROM python:3.9-slim

WORKDIR /app

COPY python/tailer.py /app/tailer.py
COPY requirements.txt /app/requirements.txt

# RUN pip install --no-cache-dir -r requirements.txt

# RUN apt-get update \
#     && apt-get install -y --no-install-recommends curl \
#     && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
#     && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
#     && apt-get clean \
#     && rm -rf /var/lib/apt/lists/*

FROM bitnami/kubectl:latest AS kubectl_source

COPY --from=kubectl_source /opt/bitnami/kubectl/bin/kubectl /usr/local/bin/kubectl

CMD ["python", "/app/tailer.py"]
