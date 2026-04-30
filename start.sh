#!/bin/bash
# City of Harare FMS — Linux/Mac Start Script
cd backend
pip install -r requirements.txt --quiet
python seed.py
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
