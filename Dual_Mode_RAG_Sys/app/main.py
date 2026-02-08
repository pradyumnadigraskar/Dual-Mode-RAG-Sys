import os
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.rag_engine import ingest_pdf, query_hybrid_rag
from fastapi.responses import RedirectResponse
import requests 
import uvicorn
import sys
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Mount static files (Frontend)
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# CORS (Allow frontend to talk to backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
async def read_root():
    return RedirectResponse(url="/static/index.html")

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Trigger Ingestion
        status = ingest_pdf(file_path)
        return {"filename": file.filename, "status": "Successfully ingested into Vector DB", "details": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/chat")
async def chat(query: str = Form(...), model_type: str = Form(...)):
    try:
        answer = query_hybrid_rag(query, model_type)
        return {"answer": answer}
    except Exception as e:
        # CHANGED: Print the error to the terminal AND return it to the UI
        print(f"CRITICAL ERROR: {str(e)}") 
        return {"answer": f"Error: {str(e)}"}

@app.get("/health")
async def health_check():
    """Checks if Ollama and Gemini are actually available"""
    
    # 1. Check Local (Ollama)
    local_status = False
    try:
        # Ping Ollama default port. Fast timeout (0.5s) so UI doesn't lag.
        r = requests.get("http://localhost:11434", timeout=0.5)
        if r.status_code == 200:
            local_status = True
    except:
        local_status = False

    # 2. Check Cloud (Gemini)
    # We check if Key exists. (For a stricter check, we could make a dummy API call)
    cloud_status = False
    if os.getenv("GEMINI_API_KEY"):
        cloud_status = True

    return {"local": local_status, "cloud": cloud_status}

