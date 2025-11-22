from time import time
from fastapi import FastAPI
from pydantic import BaseModel
import requests
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, HTTPException
import psycopg2
from dotenv import load_dotenv
from google import genai
from google.genai import types
import json

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import time 

from supabase import create_client, Client
#adding rate limiting
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# === ENVIRONMENT VARIABLES ===
load_dotenv()




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

tools_call = [
    {
        "name": "build_vidking_embed",
        "description": "Use when category is Movie or TV. Builds an embed URL for a movie or TV show given its title and category using TMDB ID and vidking url.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title of movie or TV show or Anime"},
                "category": {"type": "string", "description": 'Category: either "movie" or "tv"'},
                "season": {"type": "integer", "description": "Season number (for TV shows only, optional)"},
                "episode": {"type": "integer", "description": "Episode number (for TV shows only, optional)"}
            },
            "required": ["title", "category"]
        }
    },
    {
        "name": "get_sport_stream",
        "description": "Use when category is Sports. Gets a sports stream URL given the team name or event name.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Name of the sports team or event"}
                },
                "required": ["title"]
            }
    }
]

tools = types.Tool(function_declarations=tools_call)
config = types.GenerateContentConfig(tools=[tools])
# === GEMINI PARSING (plain text parsing) ===
def extract_and_build(user_input: str, category: str):
    prompt = f"""
    Your job: 
    - Do not ever return "I couldnt find movie or tv show" just return what you think is the title
    - Identify the **intended movie, TV show, or sports team** mentioned by the user.
    - If the user uses an approximate, shortened, or incorrect title, infer the closest title.
    Examples:
    - "fast and furious" → "The Fast and the Furious" 
    - "cowboys game" → "Dallas Cowboys"
    The category is "{category}". 
    Extract only the title and any season/episode numbers if relevant.
    User said: "{user_input}"
    """
    response = generate_retry(prompt, config)
    print(response)
    #when using tools gemini will produce list of possible tool calls
    if response.candidates[0].content.parts[0].function_call:
        function_call = response.candidates[0].content.parts[0].function_call
        if function_call:
            
            if function_call.name == "build_vidking_embed":
                return build_vidking_embed(function_call.args, function_call.args["category"])
            elif function_call.name == "get_sport_stream":
                return get_sport_stream(function_call.args["title"])
    return None 

def generate_retry(prompt, config, retries = 3, delay = 2):
    for i in range(retries):
        try:
            return gem_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config
            )
            
        except Exception as e:
            print(f"Attempt {i+1} failed: {e}")
            time.sleep(delay)
            delay *= 2
    raise Exception("Failed to generate content after retries")

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
            #so data is a dict with results list need to get that first
            results = data.get("results", [])
            results = results[0:4]
            sorted_results = sorted(results, key=lambda x: x["vote_count"], reverse=True)
            
            if sorted_results:
                return sorted_results[0]["id"]
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
                #"?autoPlay=true&nextEpisode=true&episodeSelector=true"
            )
    return None

"""# === SPORTS LOOKUP ===
def get_sport_stream(title: str):
    conn = psycopg2.connect(
        os.getenv("DB_URL")
        )
    cur = conn.cursor()
    cur.execute(
                #SELECT sources, source_id
                #FROM streams
                #WHERE title ILIKE %s
                #LIMIT 1
                ,(f"%{title}%",))
    result = cur.fetchone()
    cur.close()
    conn.close()

    if result:
        source_name, id_name = result
        url = f"https://embedsports.top/embed/{source_name}/{id_name}/1"
        return url
    return None"""

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    
def get_sport_stream(title: str):
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    pattern = f"%{title}%"
    resp = supabase.table('streams').select('sources, source_id').ilike("title", pattern).limit(1).execute()
    
    result = resp.data[0] if resp.data else None

    if result:
        source_name, id_name = result.get("sources"), result.get("source_id")
        url = f"https://embedsports.top/embed/{source_name}/{id_name}/1"
        return url
    return None


# === MAIN ROUTE ===

@app.post("/watch")
@limiter.limit("50/minute")
def watch(request: Request, req: QueryRequest):
    category = req.category.lower()
    url = extract_and_build(req.query, category)
    print("URl", url)

  
    if url:
        return {"embed_url": url, "parsed": url}
    else:
        return {"error": "No valid stream found", "parsed": url}

@app.api_route("/ping", methods=["GET", "HEAD"])
@app.get("/ping",)
def ping(request: Request):
    user_agent = request.headers.get("User-Agent", "")
    
    if "uptimerobot" not in user_agent.lower():
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"status": "ok"}



@app.get("/")
def home():
    return {"message": "AI Streaming Agent is running!"}
