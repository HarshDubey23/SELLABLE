FROM python:3.12-slim

WORKDIR /app

# Dependencies first, so a source change does not reinstall the world.
COPY apps/api/requirements.txt /app/apps/api/requirements.txt
RUN pip install --no-cache-dir -r /app/apps/api/requirements.txt

# Only what the server needs to run. Copying the whole tree would drag in
# the local virtualenv, the SQLite file and the build log.
COPY apps /app/apps
COPY missions /app/missions
COPY docs/generated /app/docs/generated
COPY pyproject.toml /app/pyproject.toml
COPY data/.gitkeep /app/data/.gitkeep

ENV PORT=8000
EXPOSE 8000

# No credentials are baked in. With none supplied the app runs on the
# simulated provider and says so on every surface.
CMD ["sh", "-c", "uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT}"]
