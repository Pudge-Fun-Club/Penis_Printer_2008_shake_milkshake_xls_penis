from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from ...services.auth import AuthService
from ..auth import auth_bypass_enabled, clear_session_cookie, session_token, set_session_cookie

router = APIRouter(tags=["auth"])


class SetupRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


@router.get("/auth/session")
def auth_session(request: Request) -> dict:
    if auth_bypass_enabled():
        return {"configured": True, "authenticated": True, "username": "dev"}
    return AuthService().status(session_token(request))


@router.post("/auth/setup")
def setup(req: SetupRequest, response: Response) -> dict:
    result = AuthService().setup(req.username, req.password)
    set_session_cookie(response, result.pop("token"))
    return result


@router.post("/auth/login")
def login(req: LoginRequest, response: Response) -> dict:
    result = AuthService().login(req.username, req.password)
    set_session_cookie(response, result.pop("token"))
    return result


@router.post("/auth/logout")
def logout(request: Request, response: Response) -> dict:
    AuthService().logout(session_token(request))
    clear_session_cookie(response)
    return {"ok": True}
