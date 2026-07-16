# TEST secret-scanning image: installs the SAME real gitleaks binary as the base
# image (containers/gitleaks/Dockerfile) and layers Python so scripts/secret_scanner.py
# and the pytest suite can drive the ACTUAL gitleaks binary (no mocks).
# Kept in lock-step with the base image's gitleaks install block (same GITLEAKS_VERSION
# and curl/tar steps) so the test image's detector is byte-identical to the hook/CI image.
FROM debian:bookworm-slim

ARG GITLEAKS_VERSION=v8.18.4
ENV GITLEAKS_VERSION=${GITLEAKS_VERSION}

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl python3 python3-pip python3-venv \
    && curl -fsSL \
        "https://github.com/gitleaks/gitleaks/releases/download/${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION#v}_linux_x64.tar.gz" \
        -o /tmp/gitleaks.tar.gz \
    && tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin gitleaks \
    && chmod +x /usr/local/bin/gitleaks \
    && rm -f /tmp/gitleaks.tar.gz \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir pytest \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /app
COPY scripts/secret_scanner.py /app/secret_scanner.py
COPY tests/test_secret_scanner.py /app/test_secret_scanner.py
COPY .gitleaks.toml /app/.gitleaks.toml

ENTRYPOINT ["/opt/venv/bin/python"]
CMD ["/app/secret_scanner.py", "--help"]
