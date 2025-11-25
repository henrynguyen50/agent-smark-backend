import json
import requests
import os
import subprocess
import psycopg2
from supabase import create_client
from dotenv import load_dotenv
load_dotenv()
STREAMD_MATCHES_API = "https://streamed.pk/api/matches/all-today"
DB_URL = os.getenv("DB_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")



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

# Supabase-backed implementations

def clear_db_supabase():
    """Delete all rows from the streams table using the Supabase client."""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    # delete all rows (use with caution)
    supabase.table('streams').delete().neq('id', 0).execute()

def query_db_supabase():
    """Fetch all rows from the streams table."""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    resp = supabase.table('streams').select('*').execute()
    # resp.data contains the list of rows
    with open('debug_records.json', 'w') as f:
            json.dump(resp.data, f, indent=4)

def update_db_supabase():
    """Fetch data from the STREAMD_MATCHES_API and update the Supabase streams table."""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    try:
        res = requests.get(STREAMD_MATCHES_API)
        res.raise_for_status()
        data = res.json()

        records = []
        for match in data:
            title = match.get('title', 'NULL')
            sources = match.get('sources', [])
            if not sources:
                continue
            for src in sources:
                records.append({
                    'title': title.lower(),
                    'sources': src.get('source'),
                    'source_id': src.get('id')
                })
        
       

        # Batch insert for efficiency
        if records:
            supabase.table('streams').insert(records).execute()

        print('Updated cache (supabase)')
    except Exception as e:
        print('Failed to update supabase cache', e)
"""def git_commit_and_push():
    try:
        subprocess.run(["git", "add", CACHE], check=True)
        subprocess.run(["git", "commit", "-m", "Update streams cache"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("Cache committed and pushed successfully")
    except subprocess.CalledProcessError as e:
        print("Git error:", e)"""
if __name__ == "__main__":
    clear_db_supabase()
    
    update_db_supabase() 
    #query_db_supabase()
    #query_db()