import json
import requests
import os
import subprocess

CACHE = "CACHE_STREAMS.json"
PPV_API = "https://ppv.to/api/streams"

def update_cache():
    try:
        res = requests.get(PPV_API)
        res.raise_for_status()
        data = res.json()

        streams = {}
        #first loop splits football basketball soccer
        #second loop gets individual streams
        for cat in data.get("streams", []):
            for stream in cat.get("streams", []):
                name = stream.get("name", "").strip()
                uri = stream.get("uri_name")
                iframe = stream.get("iframe")

                # Prefer iframe, fall back to embed link
                url = iframe or f"https://ppv.to/embed/{uri}"

                if name and url:
                    streams[name] = url
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
    update_cache()
    git_commit_and_push()
