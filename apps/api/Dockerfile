FROM python:3.11-slim
WORKDIR /app
COPY apps/api/requirements.txt /app/apps/api/requirements.txt
RUN pip install --no-cache-dir -r /app/apps/api/requirements.txt
COPY apps /app/apps
COPY tests /app/tests
COPY missions /app/missions
COPY eval /app/eval
COPY pyproject.toml /app/pyproject.toml
COPY data/.gitkeep /app/data/.gitkeep
ENV PORT=8000
EXPOSE 8000
CMD ["sh","-c","uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT}"]
