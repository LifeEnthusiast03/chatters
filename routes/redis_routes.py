from fastapi import APIRouter
from controllers.redis_controller import set_value, get_value

router = APIRouter(
    prefix="/redis",
    tags=["Redis"]
)

@router.post("/set")
async def store_data(key: str, value: str):
    return await set_value(key, value)


@router.get("/get/{key}")
async def fetch_data(key: str):
    return await get_value(key)