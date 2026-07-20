# Node 22 build/test container for the Obsidian plugin.
# Build context is the repo root so it can COPY package.json and run npm build/test.
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

# Always install devDependencies (rollup, jest, etc.) regardless of any NODE_ENV the
# host/compose leaks in. Without this, NODE_ENV=production makes `npm install` skip
# devDeps and the build/test binaries (rollup/jest) go missing -> build-app/test-app fail.
ENV NODE_ENV=development

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
# Fix npm optional dependency bug: force-install x64 native binding (compose builds arm64 on macOS, but node:22 is amd64 base)
RUN npm_config_arch=x64 npm install --no-save --force @rollup/rollup-linux-x64-gnu --loglevel=silly || true
# Create /project as symlink to /app so we can mount source files separately from node_modules
RUN ln -sf /app /project

CMD ["bash"]
