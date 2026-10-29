FROM python:3.11-slim
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .
COPY apps ./apps
ENV CHESS4F_DATA=/data PYTHONUNBUFFERED=1
CMD ["uvicorn", "chess4f.api:app", "--host", "0.0.0.0", "--port", "8000"]
