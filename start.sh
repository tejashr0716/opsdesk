#!/bin/sh
set -e
python -m scripts.seed --if-empty --with-indexes
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
