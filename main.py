from fastapi import FastAPI
from pydantic import BaseModel
import requests
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, HTTPException

from dotenv import load_dotenv
from google import genai
import json

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

#adding rate limiting
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
# === ENVIRONMENT VARIABLES ===
load_dotenv()

CACHE = "CACHE_STREAMS.json"

if os.path.exists(CACHE):
    with open(CACHE, "r") as f:
        STREAMS_CACHE = json.load(f)
origins = ["https://localhost",
           "https://localhost:8000", "http://localhost:5173", "http://127.0.0.1:3000", "https://agent-smark.vercel.app", "http://www.uptimerobot.com"]

#frontend sends a preflight security check OPTIONS request need to 
app.add_middleware(
    CORSMiddleware,
    allow_origins= origins,  # Added Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
READ_ACCESS = os.getenv("READ_ACCESS")

gem_client = genai.Client(api_key=GEMINI_KEY)

VIDKING_BASE = "https://www.vidking.net/embed"
PPV_API = "https://ppv.to/api/streams"


# === MODELS ===
class QueryRequest(BaseModel):
    category: str  # "movie" | "tv" | "sport"
    query: str


# === LIMITER ===
@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return HTTPException(status_code=429, detail="Rate limit exceeded")


# === GEMINI PARSING (plain text parsing) ===
def extract_title_gemini_plain(user_input: str, category: str):
    prompt = f"""
    You are a movie/tv/ title extractor, you are also a sports expert and can extract team names for a streaming assistant. 
    The category is "{category}". 
    Extract only the title and any season/episode numbers if relevant.
    Respond in plain text format (no JSON!):

    title: <title>
    season: <season number, optional>
    episode: <episode number, optional>

    User said: "{user_input}"
    """

    response = gem_client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    text = response.text.strip()
    print("GEMINI RESPONSE:\n", text)

    # Manual parsing
    parsed = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in ["season", "episode"]:
                try:
                    parsed[key] = int(value)
                except:
                    parsed[key] = 1
            else:
                parsed[key] = value

    return parsed


# === TMDB LOOKUPS ===
def get_tmdb_id(title: str, category: str):
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {READ_ACCESS}",
    }
    url = f"https://api.themoviedb.org/3/search/{category}?query={title}"
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            data = res.json()
            if data.get("results"):
                return data["results"][0]["id"]
    except Exception as e:
        print("TMDB API error:", e)
    return None


def build_vidking_embed(parsed, category: str):
    if category == "movie":
        tmdb_id = get_tmdb_id(parsed["title"], "movie")
        if tmdb_id:
            return f"{VIDKING_BASE}/movie/{tmdb_id}"

    elif category == "tv":
        tmdb_id = get_tmdb_id(parsed["title"], "tv")
        season = parsed.get("season", 1)
        episode = parsed.get("episode", 1)
        if tmdb_id:
            return (
                f"{VIDKING_BASE}/tv/{tmdb_id}/{season}/{episode}"
                "?autoPlay=true&nextEpisode=true&episodeSelector=true"
            )
    return None


# === SPORTS LOOKUP ===
def get_sport_stream(title: str):
    for name, url in STREAMS_CACHE.items():
        if title.lower() in name.lower():
            return url
    return None



# === MAIN ROUTE ===

@app.post("/watch")
@limiter.limit("50/minute")
def watch(request: Request, req: QueryRequest):
    category = req.category.lower()
    parsed = extract_title_gemini_plain(req.query, category)
    print("PARSED DATA:", parsed)

    url = None
    if category in ["movie", "tv"]:
        url = build_vidking_embed(parsed, category)
    elif category == "sport":
        url = get_sport_stream(parsed.get("title", ""))
    else:
        return {"error": "Invalid category", "parsed": parsed}

    if url:
        return {"embed_url": url, "parsed": parsed}
    else:
        return {"error": "No valid stream found", "parsed": parsed}

@app.api_route("/ping", methods=["GET", "HEAD"])
@app.get("/ping",)
def ping(request: Request):
    user_agent = request.headers.get("User-Agent", "")
    
    if "uptimerobot" not in user_agent.lower():
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"status": "ok"}
    return {"message": "pong"}
@app.get("/")
def home():
    return {"message": "AI Streaming Agent is running!"}
