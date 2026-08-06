"""Authentication endpoints — register, login, logout, me, GitHub OAuth.

The router adapts the identity domain to REST. Session state is carried in
an httpOnly cookie (see `_set_session_cookie`); the access token is also
returned in the body for API clients that prefer the Authorization header.
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user, get_identity_service
from app.core.config import get_settings
from app.domains.identity.ports import AuthResult
from app.domains.identity.schemas import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UserProfile,
)
from app.domains.identity.service import IdentityService
from app.models.user import User

router = APIRouter()

OAUTH_STATE_COOKIE = "evoshield_oauth_state"


def _profile_from_user(user: User) -> UserProfile:
    return UserProfile(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        auth_provider=user.auth_provider,
        created_at=user.created_at,
    )


def _auth_response(result: AuthResult) -> AuthResponse:
    return AuthResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
        user=UserProfile(
            id=result.user.id,
            email=result.user.email,
            full_name=result.user.full_name,
            avatar_url=result.user.avatar_url,
            auth_provider=result.user.provider,
        ),
    )


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.session_cookie_name, path="/")


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=201,
    summary="Register a new account",
)
async def register(
    payload: RegisterRequest,
    response: Response,
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> AuthResponse:
    result = await identity.register(payload.email, payload.password, payload.full_name)
    _set_session_cookie(response, result.access_token)
    return _auth_response(result)


@router.post("/login", response_model=AuthResponse, summary="Log in")
async def login(
    payload: LoginRequest,
    response: Response,
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> AuthResponse:
    result = await identity.login(payload.email, payload.password)
    _set_session_cookie(response, result.access_token)
    return _auth_response(result)


@router.post("/logout", response_model=MessageResponse, summary="Log out")
async def logout(
    request: Request,
    response: Response,
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> MessageResponse:
    token = request.cookies.get(get_settings().session_cookie_name)
    if token:
        await identity.logout(token)
    _clear_session_cookie(response)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserProfile, summary="Current user profile")
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserProfile:
    return _profile_from_user(user)


@router.get("/oauth/github", summary="Start GitHub OAuth flow")
async def github_oauth_start(
    response: Response,
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> RedirectResponse:
    url, state = await identity.github_authorization_url()
    redirect = RedirectResponse(url, status_code=307)
    redirect.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state,
        httponly=True,
        max_age=600,
        samesite="lax",
        path="/",
    )
    return redirect


@router.get("/oauth/github/callback", summary="GitHub OAuth callback")
async def github_oauth_callback(
    code: str,
    state: str,
    request: Request,
    identity: Annotated[IdentityService, Depends(get_identity_service)],
) -> RedirectResponse:
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if not expected_state or not secrets.compare_digest(expected_state, state):
        # State mismatch → likely CSRF or a stale/forged callback. Clear the
        # state cookie and bounce the user to the app login with an error
        # marker; never exchange the code.
        login_url = f"{get_settings().frontend_url}/login?error=oauth_failed"
        response = RedirectResponse(url=login_url, status_code=307)
        response.delete_cookie(key=OAUTH_STATE_COOKIE, path="/")
        return response

    result = await identity.github_callback(code)
    response = RedirectResponse(url=f"{get_settings().frontend_url}/app", status_code=307)
    _set_session_cookie(response, result.access_token)
    response.delete_cookie(key=OAUTH_STATE_COOKIE, path="/")
    return response


@router.get("/session/check", response_model=UserProfile, summary="Validate session")
async def session_check(
    user: Annotated[User, Depends(get_current_user)],
) -> UserProfile:
    """Validate the session cookie / bearer token. Used by the frontend."""
    return _profile_from_user(user)
