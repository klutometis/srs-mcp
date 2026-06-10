FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml ./
COPY srs_mcp ./srs_mcp
RUN uv sync

# Cards live on a persistent volume in prod so they survive redeploys.
# Mount a Railway volume at /data and keep SRS_DB pointed inside it.
ENV SRS_DB=/data/srs.db
ENV MCP_TRANSPORT=http
ENV PORT=8000
EXPOSE 8000

CMD ["uv", "run", "srs-mcp"]
