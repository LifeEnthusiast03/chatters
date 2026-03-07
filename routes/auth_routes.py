from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.controllers import auth_controller

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/signup")
def signup(user: schemas.UserSignup, db: Session = Depends(get_db)):
    return auth_controller.signup(user, db)


@router.post("/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    return auth_controller.login(user, db)