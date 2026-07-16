# BASE secret-scanning image: the real gitleaks binary (the authoritative secret
# detector). Used by git pre-commit hooks and the CI pipeline. No Python needed here.
FROM debian:bookworm-slim

ARG GITLEAKS_VERSION=v8.18.4
ENV GITLEAKS_VERSION=${GITLEAKS_VERSION}

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git \
    && curl -fsSL \
        "https://github.com/gitleaks/gitleaks/releases/download/${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION#v}_linux_x64.tar.gz" \
        -o /tmp/gitleaks.tar.gz \
    && tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin gitleaks \
    && chmod +x /usr/local/bin/gitleaks \
    && rm -f /tmp/gitleaks.tar.gz \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
ENTRYPOINT ["/usr/local/bin/gitleaks"]
CMD ["detect", "--source=/src", "--no-git", "--redact", "--report-format=json"]
