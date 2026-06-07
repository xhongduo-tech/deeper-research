from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, RecoverRequest, TokenResponse, UserInfo
from app.services.auth_service import authenticate_user, register_user, recover_password, create_access_token
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, data.auth_id, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="统一认证ID或密码错误",
        )
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(
        access_token=token,
        username=user.username,
        role=user.role,
    )


@router.post("/register")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await register_user(
            db, data.auth_id, data.username, data.department,
            data.scene, data.description, data.password,
        )
        return {"message": "注册成功", "username": user.username}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/recover")
async def recover(data: RecoverRequest, db: AsyncSession = Depends(get_db)):
    try:
        new_password = await recover_password(
            db, data.auth_id, data.username, data.department, data.scene,
        )
        return {"message": f"密码已重置，新密码为: {new_password}", "new_password": new_password}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/me", response_model=UserInfo)
async def get_me(current_user=Depends(get_current_user)):
    return current_user
