@echo off

cd C:\Users\JN\agent-smark-backend

python update_cache.py

git add .

git commit -m "Auto update cache"

git push origin main

