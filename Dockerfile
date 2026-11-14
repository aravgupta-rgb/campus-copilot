# Campus Copilot: agent API + web app in one Cloud Run container.

# 1) Build the web app
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Same origin as the API in production. Pick the design at build time:
#   bold/default = orange (5173) · bold/navy = navy (5175) · aurora/default = ocean (5174)
ARG VITE_SKIN=bold
ARG VITE_PALETTE=navy
ENV VITE_API_URL=/ VITE_SKIN=${VITE_SKIN} VITE_PALETTE=${VITE_PALETTE}
RUN npm run build

# 2) Python server with the ADK agents
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY agent/ ./agent/
COPY server.py ./
COPY --from=web /web/dist ./frontend/dist
EXPOSE 8080
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}"]
