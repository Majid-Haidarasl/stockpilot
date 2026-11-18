# Pin to a tag present on the developer machine when Hub is rate-limited (3.13-slim cached).
FROM python:3.13-slim

WORKDIR /load
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY auth.py locustfile.py cleanup_reserved.py analyze_phases.py smoke_login.py ./

# Results written to bind-mounted /results
ENV STOCKPILOT_LOAD_BASE=https://stockpilot.local
ENV STOCKPILOT_LOAD_AUTH_HOST=auth.stockpilot.local
ENV STOCKPILOT_LOAD_RESULTS_DIR=/results

# Default: Locust. Override entrypoint for cleanup_reserved.py / analyze_phases.py.
ENTRYPOINT ["locust", "-f", "locustfile.py", "--host", "https://stockpilot.local"]
