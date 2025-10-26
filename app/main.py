from typing import Union
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .connection import init_db, close_db

app = FastAPI(root_path="/api/1")

# CORS setup

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Links de donde se permiten requests
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    init_db()

@app.get("/")
def Health():
    return {"status": "healthy"}

@app.get("/ping")
def ping():
    return {"ping": "pong!"}


@app.get("/items/{item_id}") # Aqui va la ruta del url a la que se hace el request
def read_item(item_id: int, q: Union[str, None] = None): # Los parametros que recibe el request
    # La logica del request
    return {"item_id": item_id, "q": q} # Lo que retorna el request

@app.on_event("shutdown")
async def shutdown_event():
    close_db()