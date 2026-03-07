from fastapi import FastAPI
from routes.redis_routes import router as redis_router

app = FastAPI()

app.include_router(redis_router)

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}
# @app.post("/whatsapp/callback"):
# def getwhatsapp
