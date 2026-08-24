# One shared image for both the web and admin services (AE-06: "gemeinsames
# Basis-Image ... aber keine Laufzeit") — docker-compose.yml runs this image
# twice with a different `command:` per service.
FROM python:3.12-slim

# git is required at runtime, not just build time: admin/versioning.py shells
# out to it to keep the content directory as a local git repo (FA-41).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/portfolio

COPY requirements.txt requirements-admin.txt ./
RUN pip install --no-cache-dir -r requirements-admin.txt

COPY shared ./shared
COPY web ./web
COPY admin ./admin
COPY wsgi_web.py wsgi_admin.py ./

RUN useradd --uid 1000 --create-home portfolio
USER portfolio

EXPOSE 8000
