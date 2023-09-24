FROM python:3.9
LABEL authors="maxemiliang"

WORKDIR /app

COPY requirements.txt requirements.txt
COPY run_benchmark.py run_benchmark.py

ENTRYPOINT ["python", "run_benchmarks.py"]
