# Narrow overlay on the deployed v0.21.0 maintenance image. No dependency changes.
FROM ghcr.io/tacodong/hermes-agent@sha256:ad4caba252b76eb8ebd26e39d2a4cdedccdf52413987a7683724841794a05159
ARG HERMES_GIT_SHA
LABEL org.opencontainers.image.source="https://github.com/tacodong/hermes-agent"
LABEL org.opencontainers.image.revision=$HERMES_GIT_SHA
COPY tools/approval_context.py tools/process_registry.py tools/bot_mode_dm.py tools/file_operations.py /opt/hermes/tools/
COPY tui_gateway/methods_prompt.py tui_gateway/session_workdir.py /opt/hermes/tui_gateway/
COPY agent/file_safety.py /opt/hermes/agent/
COPY hermes_cli/config.py /opt/hermes/hermes_cli/
