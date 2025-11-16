import json
import requests
import os
import subprocess
import psycopg2
from dotenv import load_dotenv
load_dotenv()
STREAMD_MATCHES_API = "https://streamed.pk/api/matches/all-today"
DB_URL = os.getenv("DB_URL")
print(DB_URL)


def init_db():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
            CREATE TABLE IF NOT EXISTS streams (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                sources TEXT,
                source_id TEXT
            )
        """)
    conn.commit()
    conn.close()

def clear_db():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("DELETE FROM streams")
    conn.commit()
    conn.close()
def query_db():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
            SELECT *
            from streams
        """)
    rows = cur.fetchall()
    print(rows)
    conn.close()
def update_cache():
    try:
        res = requests.get(STREAMD_MATCHES_API)
        res.raise_for_status()
        data = res.json()

        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        for match in data:
            title = match.get("title", "NULL")
            sources = match.get("sources", [])
            if not sources:
                continue
            for src in sources:
                source_name = src.get("source")
                source_id = src.get("id")
                cur.execute("INSERT INTO streams (title, sources, source_id) VALUES (%s, %s, %s)", 
                            (title, src.get("source"), src.get("id")),
                            )

            
        conn.commit()
        conn.close()
        print("Updated cache")
    except Exception as e:
        print("Failed to get streams", e)
"""def git_commit_and_push():
    try:
        subprocess.run(["git", "add", CACHE], check=True)
        subprocess.run(["git", "commit", "-m", "Update streams cache"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("Cache committed and pushed successfully")
    except subprocess.CalledProcessError as e:
        print("Git error:", e)"""
if __name__ == "__main__":
    clear_db()
    init_db()
    update_cache()  
    
    #query_db()