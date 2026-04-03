#!/bin/bash
set -e
cd backend
python database.py
python seed.py
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
