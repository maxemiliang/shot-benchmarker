FROM python:3-buster AS builder
ADD . /app
WORKDIR /app

# Install git
RUN apt-get update && apt-get install -y git

# We are installing a dependency here directly into our app source dir
RUN pip install --target=/app -r requirements.txt
ENTRYPOINT ["python", "/app/main.py"]
