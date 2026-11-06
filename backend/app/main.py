
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

# Initialisation de l'application FastAPI
app = FastAPI(
    title="API Pisciculture Intelligente",
    description="API de gestion et de surveillance piscicole multi-bassins",
    version="1.0.0"
)

# Autoriser le frontend React à communiquer avec FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

@app.get("/")
def accueil():
    return {
        "message": "Bienvenue dans l'API Pisciculture Intelligente",
        "status": "success",
        "version": "1.0.0"
    }

app.include_router(router)

@app.get("/health")
def verifier_sante():
    return {
        "status": "ok",
        "service": "FastAPI Pisciculture"
    }
