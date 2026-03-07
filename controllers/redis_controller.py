from fastapi import HTTPException
from redis.redis_client import redis_client


async def set_value(key: str, value: str):
    await redis_client.set(key, value)
    return {"message": "Value stored successfully"}


async def get_value(key: str):
    value = await redis_client.get(key)

    if value is None:
        raise HTTPException(status_code=404, detail="Key not found")

    return {"key": key, "value": value}