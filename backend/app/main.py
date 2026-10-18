import asyncio
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from fastapi.requests import Request
from app.api import users, boosts, game, tasks, rating, bonus, wallet
from app.api import mining, ogpass, withdraw
from app.api import admin as admin_api
from app.api import admin_ext as admin_ext_api
from app.api.features import arcade_router, button_router, drops_router
from app.background.passive_income import apply_passive_income
from app.background.energy import restore_energy_task
from app.database import AsyncSessionLocal

# Инициализация приложения FastAPI
app = FastAPI(
    title="SpaceHunter API",
    description="Бэкенд для Telegram Mini App с NFT и TON-кошельком",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.tgspacehunter.ru",
        "https://dedovinside.github.io",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Telegram-Init-Data"],
)


@app.middleware("http")
async def telegram_auth_middleware(request: Request, call_next):
    """When SPACEHUNTER_AUTH=on, every /api request must carry a valid
    Telegram-signed initData header, and the identity the request acts as
    must match the verified user:
    - admin routes: the claimed admin_id (or telegram_id on whoami) must
      BE the verified user — you cannot sign as yourself and claim to be
      the admin in the body;
    - other routes: the subject telegram_id (first id-shaped path segment,
      query, or JSON body) must be the verified user.
    The bot itself may register referrals server-side by presenting the
    bot token in X-Bot-Token (it is a trusted server-side actor)."""
    import json as _json

    from app.services.auth import auth_required, verify_init_data, _bot_token
    import hmac as _hmac

    if not auth_required():
        return await call_next(request)
    path = request.url.path
    if not path.startswith("/api/"):
        return await call_next(request)
    if path == "/api/admin/announcement" and request.method == "GET":
        return await call_next(request)  # public banner read

    bot_token = _bot_token()
    presented = request.headers.get("x-bot-token", "")
    # The bot token is a scoped server-side credential: it may ONLY register
    # users (its /start referral flow). On every other path it counts for
    # nothing — a leaked token must not become a skeleton key for the API.
    _BOT_PATHS = {"/api/users/register", "/api/users/register_with_referral"}
    if (bot_token and presented and _hmac.compare_digest(presented, bot_token)
            and request.method == "POST" and path in _BOT_PATHS):
        return await call_next(request)  # trusted server-side bot call

    uid = verify_init_data(request.headers.get("x-telegram-init-data", ""))
    if uid is None:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing Telegram init data"})

    body_claims: dict = {}
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        raw = await request.body()
        if raw:
            try:
                data = _json.loads(raw)
                if isinstance(data, dict):
                    body_claims = data
            except Exception:
                pass

    def _parse_claim(v):
        """Normalise one raw identity-claim value to an int (None = absent).
        Raises ValueError when a claim is present but not a clean integer —
        the handlers coerce values like "+123" or "123" via Pydantic/FastAPI,
        so anything the handler would accept must be compared here too."""
        if v is None:
            return None
        if isinstance(v, bool):
            raise ValueError("boolean claim")
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            if v.is_integer():
                return int(v)
            raise ValueError("non-integral claim")
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("+"):
                s = s[1:]
            if s and s.isascii() and s.isdigit():
                return int(s)
            raise ValueError("malformed claim")
        raise ValueError("unsupported claim type")

    def collect_claims(key: str) -> list:
        """EVERY occurrence of the claim — query (all values) and JSON body.
        Checking only the first hit lets a matching query value shadow a
        foreign body value the handler actually reads."""
        vals = []
        for raw in request.query_params.getlist(key):
            parsed = _parse_claim(raw)
            if parsed is not None:
                vals.append(parsed)
        if key in body_claims:
            parsed = _parse_claim(body_claims.get(key))
            if parsed is not None:
                vals.append(parsed)
        return vals

    try:
        admin_claims = collect_claims("admin_id")
        subject_claims = collect_claims("telegram_id")
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Malformed identity claim"})

    if path.startswith("/api/admin/"):
        claims = admin_claims + subject_claims
        if not claims or any(c != uid for c in claims):
            return JSONResponse(status_code=403, content={"detail": "Telegram identity mismatch"})
    else:
        # An admin_id claimed on ANY route (e.g. task creation lives outside
        # /admin but trusts admin_id) is an actor claim: it must be the signer.
        if any(c != uid for c in admin_claims):
            return JSONResponse(status_code=403, content={"detail": "Telegram identity mismatch"})
        if subject_claims and any(c != uid for c in subject_claims):
            return JSONResponse(status_code=403, content={"detail": "Telegram identity mismatch"})
        # The path check runs ALWAYS in the non-admin branch — never as an
        # alternative to the claim check. A matching telegram_id claim must not
        # suppress it, or a signed user could reach path-parameter endpoints
        # (e.g. GET /api/game/state/{other_id}) belonging to another user.
        for seg in path.split("/"):
            if seg.isdigit() and len(seg) >= 5:
                if int(seg) != uid:
                    return JSONResponse(status_code=403, content={"detail": "Telegram identity mismatch"})
                break
    # Ban enforcement: a suspended account's signed requests are refused
    # everywhere (admin routes included only via the allowlist anyway).
    if not path.startswith("/api/admin/"):
        try:
            from sqlalchemy import select as _select

            from app.database import AsyncSessionLocal
            from app.models.user import User as _User

            async with AsyncSessionLocal() as _db:
                _banned = (await _db.execute(
                    _select(_User.banned).where(_User.telegram_id == uid)
                )).scalar_one_or_none()
            if _banned:
                return JSONResponse(status_code=403, content={"detail": "Account suspended"})
        except Exception:
            pass  # a ban-check failure must never lock everyone out
    request.state.telegram_id = uid
    return await call_next(request)

# Подключаем маршруты
app.include_router(users.router, prefix="/api")
app.include_router(boosts.router, prefix="/api")
app.include_router(game.router, prefix="/api/game")
app.include_router(tasks.router, prefix="/api")
app.include_router(rating.router, prefix="/api")
app.include_router(bonus.router, prefix="/api")
app.include_router(wallet.router, prefix="/api")
app.include_router(mining.router, prefix="/api")
app.include_router(ogpass.router, prefix="/api")
app.include_router(withdraw.router, prefix="/api")
app.include_router(arcade_router, prefix="/api")
app.include_router(button_router, prefix="/api")
app.include_router(drops_router, prefix="/api")
app.include_router(admin_api.router, prefix="/api")
app.include_router(admin_ext_api.router, prefix="/api")

# Глобальный список фоновых тасков
background_tasks = []

# Dependency для получения асинхронной сессии базы данных
async def get_db():
    async with AsyncSessionLocal() as db:
        yield db

# Главная страница
@app.get("/")
def read_root():
    return {"message": "Welcome to the game backend!"}

# Запускаем фоновый процесс пассивного дохода
@app.on_event("startup")
async def startup_event():
    try:
        # Запуск задачи пассивного дохода
        passive_income_task = asyncio.create_task(apply_passive_income())
        background_tasks.append(passive_income_task)

        # Запуск задачи восстановления энергии
        energy_task = asyncio.create_task(restore_energy_task())
        background_tasks.append(energy_task)
        
        print("Background tasks started successfully")
    except Exception as e:
        print(f"Error starting background tasks: {e}")

# Завершаем фоновые процессы при остановке сервера
@app.on_event("shutdown")
async def shutdown_event():
    for task in background_tasks:
        task.cancel()
    # Ждем завершения всех задач
    await asyncio.gather(*background_tasks, return_exceptions=True)
