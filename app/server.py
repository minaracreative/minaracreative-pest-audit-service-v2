from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI()

# Mount the main audit API
from app.main import app as audit_app
app.mount("/api", audit_app)

# Serve the form
@app.get("/")
async def serve_form():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
