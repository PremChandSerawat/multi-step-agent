## Multi-stage build for frontend (Next.js) and backend (FastAPI)

# ---------- Frontend build ----------
FROM node:20-bookworm AS frontend-build
WORKDIR /app/frontend

# Install dependencies and build the Next.js app
COPY frontend/package*.json ./
RUN npm ci

COPY frontend .
RUN npm run build


# ---------- Final runtime (Node + Python) ----------
FROM node:20-bookworm-slim AS runner
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_BASE=http://localhost:8000 \
    DOTENV_VERBOSITY=0

# Install Python for the FastAPI backend
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Backend dependencies (install inside venv to avoid PEP 668 issue)
COPY backend/requirements.txt backend/requirements.txt
RUN python3 -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && pip install --no-cache-dir -r backend/requirements.txt
ENV PATH="/opt/venv/bin:${PATH}"

# Backend source
COPY backend /app/backend

# Frontend production artifacts
COPY --from=frontend-build /app/frontend/.next /app/frontend/.next
COPY --from=frontend-build /app/frontend/public /app/frontend/public
COPY --from=frontend-build /app/frontend/node_modules /app/frontend/node_modules
COPY --from=frontend-build /app/frontend/package*.json /app/frontend/
COPY --from=frontend-build /app/frontend/next.config.ts /app/frontend/
COPY --from=frontend-build /app/frontend/tsconfig.json /app/frontend/

# Expose frontend and backend ports
EXPOSE 3000
EXPOSE 8000

# Start both services (FastAPI + Next.js)
CMD ["bash", "-c", "uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 & cd /app/frontend && npm run start -- --hostname 0.0.0.0 --port 3000"]
