FROM node:22.11.0

ARG REPO_NAME
ENV REPO_NAME=${REPO_NAME}

ARG TAG
ENV TAG=${TAG}

RUN apt-get update && apt-get install -y \
    git \
    curl \
    zip \
    dos2unix

WORKDIR /app

RUN npm install -g @commitlint/cli @commitlint/config-conventional && \
    commitlint --version || { echo "commitlint install failed"; exit 1; }

RUN curl -sL --retry 3 -o git-chglog.tar.gz https://github.com/git-chglog/git-chglog/releases/download/v0.15.4/git-chglog_0.15.4_linux_amd64.tar.gz || { echo "curl failed to download git-chglog"; exit 1; } && \
    [ $(stat -c %s git-chglog.tar.gz) -gt 1000000 ] || { echo "git-chglog.tar.gz too small, likely corrupted"; ls -l git-chglog.tar.gz; cat git-chglog.tar.gz; exit 1; } && \
    tar xzf git-chglog.tar.gz || { echo "tar failed to extract git-chglog.tar.gz"; ls -l; exit 1; } && \
    mv git-chglog /usr/local/bin/ && \
    chmod +x /usr/local/bin/git-chglog && \
    rm git-chglog.tar.gz && \
    git-chglog --version || { echo "git-chglog install failed"; exit 1; }

COPY package.json .
RUN npm install --no-package-lock --loglevel=silly

CMD ["bash"]
