from fastapi import APIRouter, Request
from authlib.integrations.starlette_client import OAuth

router = APIRouter()

oauth = OAuth()

# ─────────────────────────────
# GOOGLE OAUTH CONFIG
# ─────────────────────────────
oauth.register(
    name="google",
    client_id="GOOGLE_CLIENT_ID",
    client_secret="GOOGLE_CLIENT_SECRET",
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    access_token_url="https://oauth2.googleapis.com/token",
    client_kwargs={"scope": "openid email profile"},
)

# ─────────────────────────────
# FACEBOOK OAUTH CONFIG
# ─────────────────────────────
oauth.register(
    name="facebook",
    client_id="FACEBOOK_APP_ID",
    client_secret="FACEBOOK_APP_SECRET",
    authorize_url="https://www.facebook.com/dialog/oauth",
    access_token_url="https://graph.facebook.com/oauth/access_token",
    client_kwargs={"scope": "email"},
)


# ─────────────────────────────
# GOOGLE LOGIN
# ─────────────────────────────
@router.get("/google/login")
async def google_login(request: Request):

    redirect_uri = request.url_for("google_auth")

    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/auth")
async def google_auth(request: Request):

    token = await oauth.google.authorize_access_token(request)

    user = await oauth.google.parse_id_token(request, token)

    return {"user": user}


# ─────────────────────────────
# FACEBOOK LOGIN
# ─────────────────────────────
@router.get("/facebook/login")
async def facebook_login(request: Request):

    redirect_uri = request.url_for("facebook_auth")

    return await oauth.facebook.authorize_redirect(request, redirect_uri)


@router.get("/facebook/auth")
async def facebook_auth(request: Request):

    token = await oauth.facebook.authorize_access_token(request)

    user = await oauth.facebook.get("me?fields=id,name,email")

    return user.json()