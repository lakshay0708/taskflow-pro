# main.py

from fastapi import FastAPI

app = FastAPI(title="TaskFlow Pro")

@app.get("/api/ping")
def ping():
    return {
        "status": "ok",
        "message": "TaskFlow Pro server is alive"
    }