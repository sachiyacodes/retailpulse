FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements-lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements-lock.txt

COPY pyproject.toml ./
COPY src ./src
COPY sql ./sql
COPY .streamlit ./.streamlit
RUN python -m pip install --no-cache-dir --no-deps -e . \
    && useradd --uid 10001 --create-home retailpulse \
    && chown -R retailpulse:retailpulse /app

USER retailpulse
RUN python -m retailpulse.pipeline --output data/processed

EXPOSE 8501
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"

ENTRYPOINT ["python", "-m", "streamlit"]
CMD ["run", "src/retailpulse/dashboard.py", "--server.address=0.0.0.0", "--server.port=8501", "--browser.gatherUsageStats=false"]
