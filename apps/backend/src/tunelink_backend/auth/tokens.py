from datetime import UTC, datetime, timedelta
from uuid import UUID

from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import OctKey
from joserfc.jwt import JWTClaimsRegistry

from tunelink_backend.config import get_settings


def _key() -> OctKey:
    return OctKey.import_key(get_settings().jwt_secret)


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "iss": settings.jwt_issuer,
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.session_max_age_seconds)).timestamp()),
    }
    return jwt.encode({"alg": "HS256"}, payload, _key())


def parse_access_token(token: str) -> UUID:
    settings = get_settings()
    try:
        token_obj = jwt.decode(token, _key())
        JWTClaimsRegistry(
            iss={"essential": True, "value": settings.jwt_issuer},
            sub={"essential": True},
            exp={"essential": True},
        ).validate(token_obj.claims)
    except (JoseError, ValueError, KeyError) as exc:
        raise ValueError("invalid token") from exc
    return UUID(str(token_obj.claims["sub"]))
