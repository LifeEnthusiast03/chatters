from fastapi import APIRouter, Depends
from controllers.redis_controller import set_value, get_value
from security.jwt_auth import verify_jwt

router = APIRouter(
    prefix="/redis",
    tags=["Redis"]
)

@router.post("/set")
async def store_data(key: str, value: str, user=Depends(verify_jwt)):
    return await set_value(key, value)


@router.get("/get/{key}")
async def fetch_data(key: str, user=Depends(verify_jwt)):
    return await get_value(key)