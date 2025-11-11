import json
import requests
import os
import subprocess

CACHE = "CACHE_STREAMS.json"
STREAMD_MATCHES_API = "https://streamed.pk/api/matches/live"
STREAMD_STREAMS_API = "https://streamed.pk/api/stream/"

def update_cache():
    try:
        res = requests.get(STREAMD_MATCHES_API)
        res.raise_for_status()
        data = res.json()

        streams = {}
        #first loop splits football basketball soccer
        #second loop gets individual streams
        for match in data:
            title = match.get("title", "NULL")
            sources = match.get("sources", [])
            if not sources:
                continue
            source_array = []
            for src in sources:
                source_array.append({
                    "source": src.get("source"),
                    "id": src.get("id") 
                    })
            streams[title] = source_array

            
        with open("CACHE_STREAMS.json", "w") as f:
            json.dump(streams, f, indent=2)
    except Exception as e:
        print("Failed to get streams", e)
def git_commit_and_push():
    try:
        subprocess.run(["git", "add", CACHE], check=True)
        subprocess.run(["git", "commit", "-m", "Update streams cache"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("Cache committed and pushed successfully")
    except subprocess.CalledProcessError as e:
        print("Git error:", e)
if __name__ == "__main__":
    os.remove(CACHE)
    update_cache()
    #git_commit_and_push()
    