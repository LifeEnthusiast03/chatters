from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}
# @app.post("/whatsapp/callback"):
# def getwhatsapp
