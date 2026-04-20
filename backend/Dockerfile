FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
  && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt

RUN pip install uv

# Install torch separately to handle the CPU-only requirement first
RUN uv pip install --system torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install all other requirements in one go without cache to prevent the 'proxy' error
RUN uv pip install --system --no-cache -r /app/requirements.txt

# Pre-download the model weights
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY backend /app/backend
COPY ingestion /app/ingestion
COPY parser /app/parser
COPY data /app/data

ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=1

EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
