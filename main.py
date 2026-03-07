from fastapi import FastAPI
from routes.redis_routes import router as redis_router
from routes import auth_routes
from database.postgres_client import engine,Base
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.include_router(redis_router)
app.include_router(auth_routes.router)

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}
# @app.post("/whatsapp/callback"):
# def getwhatsapp
