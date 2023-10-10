FROM python:3-buster AS builder
ADD . .

# Install git
RUN apt-get update && apt-get install -y git

# We are installing a dependency here directly into our app source dir
RUN pip install -r requirements.txt
ENTRYPOINT ["python", "main.py"]
