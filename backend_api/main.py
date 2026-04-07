# 

from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/")
def root():
    return {"message": "working"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
def startup():
    print("🚀 APP STARTED")
    print("PORT:", os.environ.get("PORT"))