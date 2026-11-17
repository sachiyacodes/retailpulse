# Local deployment and container checks

The dashboard can run locally without an account, GitHub repository, database, or public hosting. Nothing in these commands publishes the project. See [verification.md](verification.md) for executed checks; source files and static validation do not prove a container has run.

## Run without Docker

After the README's Python installation, run from the repository root:

```bash
python -m retailpulse.pipeline
python -m streamlit run src/retailpulse/dashboard.py --server.address 127.0.0.1 --server.port 8501
```

Open [the local dashboard](http://127.0.0.1:8501). Ctrl+C stops it. This binds only to your machine. The default data is a seeded synthetic demonstration.

## Run the dashboard container

Install Docker Desktop with a supported Linux-container backend first. On Windows, Docker's WSL 2 backend needs WSL 2 and its operating-system prerequisites; installation can require administrator access or a restart. Follow [Docker's Windows installation guide](https://docs.docker.com/desktop/setup/install/windows-install/) rather than assuming that a Compose file alone supplies the engine.

From the repository root:

```bash
docker compose --profile dashboard up -d --build --wait dashboard
docker compose ps
```

Open [the local dashboard](http://127.0.0.1:8501). The port binds to `127.0.0.1`; other machines cannot access it through this mapping. The dashboard service has no PostgreSQL dependency because it reads processed files. Building generates its own synthetic data; local datasets, `.env` files and PBIX files are excluded from the build context.

```bash
docker compose logs dashboard
docker compose stop dashboard
```

`docker compose down` removes the project's containers and network while retaining the PostgreSQL named volume. Do not add `--volumes` unless you intend to delete that database's stored data.

The image runs as an unprivileged user, serves port 8501, and exposes a health check at `/_stcore/health`. It installs the same exact dependency pins used by local verification. The lock file includes the small development tools so there is one dependency list to maintain.

## Use already processed external data

Run the pipeline outside the container first, inspect its provenance and quality report, then mount the processed directory read-only. This PowerShell example uses `data/uci`; change the host path to your actual output directory:

```powershell
$processedPath = (Resolve-Path data/uci).Path
docker build -t retailpulse:local .
docker run --rm --name retailpulse-dashboard -p 127.0.0.1:8501:8501 --mount "type=bind,source=$processedPath,target=/data,readonly" -e RETAILPULSE_DATA_DIR=/data retailpulse:local
```

macOS/Linux equivalent:

```bash
docker build -t retailpulse:local .
docker run --rm --name retailpulse-dashboard -p 127.0.0.1:8501:8501 --mount "type=bind,source=$(pwd)/data/uci,target=/data,readonly" -e RETAILPULSE_DATA_DIR=/data retailpulse:local
```

Stop this foreground container with Ctrl+C. Confirm that the mounted folder includes `transactions.csv`, `manifest.json`, `forecast.csv` and `forecast_metrics.json`. Mounting a directory does not certify its source or metric definitions.

## PostgreSQL and checks

The original database-only command remains unchanged:

```bash
docker compose up -d --wait postgres
```

Set `DATABASE_URL`, then use the loader and tests from the README. Tests replace the dedicated RetailPulse snapshot with a small fixture; reload your chosen dataset afterward. The dashboard container does not automatically load PostgreSQL or use its credentials.

Validate the Compose model without starting containers:

```bash
docker compose --profile dashboard config --quiet
```

This checks configuration only. A live build and HTTP check require a working Docker engine:

```bash
docker build -t retailpulse:local .
docker run -d --name retailpulse-check -p 127.0.0.1:8501:8501 retailpulse:local
docker inspect --format '{{.State.Health.Status}}' retailpulse-check
```

Wait for `healthy`, inspect logs if it fails, then remove only that test container with `docker rm -f retailpulse-check`.

## CI and public hosting status

The GitHub Actions workflow runs Python checks, live PostgreSQL integration, a Docker image build and a local HTTP smoke check. `workflow_dispatch` allows a manual run after the workflow exists in a GitHub repository. No workflow has been uploaded or triggered here, and no push is required for local validation. A local workflow linter cannot prove GitHub-hosted execution.

Public hosting is separate from local deployment. It requires a chosen provider, account access, and any applicable cost or data-sharing decisions. The supplied image is a deployable source artifact, not a claim of an online endpoint. Do not expose the PostgreSQL port or development password publicly. Keep public demos synthetic unless the source data is approved for sharing.
