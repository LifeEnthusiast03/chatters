from sqlalchemy.orm import Session
from fastapi import HTTPException
from model import model
from schema import schemas
from security.jwt_auth import hash_password, verify_password, create_access_token


def signup(user: schemas.UserSignup, db: Session):

    existing_user = db.query(model.User).filter(
        model.User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_pw = hash_password(user.password)

    new_user = model.User(
        username=user.username,
        email=user.email,
        password=hashed_pw
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User created successfully"}


def login(user: schemas.UserLogin, db: Session):

    db_user = db.query(model.User).filter(
        model.User.email == user.email
    ).first()

    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({
        "user_id": db_user.id,
        "email": db_user.email
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }