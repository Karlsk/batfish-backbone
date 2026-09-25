from fastapi import APIRouter, Request, Response

from app.modules.auth.schemas import LoginRequest, PasswordRequest, SessionInfo
from app.modules.auth.service import AuthService

COOKIE = "batfish_session"


def create_router(service: AuthService, *, secure_cookie: bool) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["Authentication"])

    @router.post("/login", response_model=SessionInfo)
    def login(body: LoginRequest, request: Request, response: Response):
        info, token = service.login(
            body.username,
            body.password.get_secret_value(),
            origin=request.headers.get("origin"),
            client_address=request.client.host if request.client else "unknown",
        )
        response.set_cookie(
            COOKIE,
            token,
            max_age=28800,
            httponly=True,
            secure=secure_cookie,
            samesite="lax",
            path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        return info

    @router.get("/me", response_model=SessionInfo)
    def me(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        return service.me(request.cookies.get(COOKIE))

    @router.post("/logout", status_code=204)
    def logout(request: Request):
        service.logout(
            request.cookies.get(COOKIE),
            origin=request.headers.get("origin"),
            csrf_token=request.headers.get("x-csrf-token"),
        )
        response = Response(status_code=204, headers={"Cache-Control": "no-store"})
        response.delete_cookie(
            COOKIE, httponly=True, secure=secure_cookie, samesite="lax", path="/"
        )
        return response

    @router.post("/password", status_code=204)
    def password(body: PasswordRequest, request: Request):
        service.change_password(
            request.cookies.get(COOKIE),
            body.current_password.get_secret_value(),
            body.new_password.get_secret_value(),
            origin=request.headers.get("origin"),
            csrf_token=request.headers.get("x-csrf-token"),
        )
        response = Response(status_code=204, headers={"Cache-Control": "no-store"})
        response.delete_cookie(
            COOKIE, httponly=True, secure=secure_cookie, samesite="lax", path="/"
        )
        return response

    return router
