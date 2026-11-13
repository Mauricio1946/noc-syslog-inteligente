"""Autenticación por cookie de sesión y control de acceso por roles.

- La cookie es HttpOnly (JavaScript no puede leerla) y SameSite=Strict
  (el navegador no la envía desde otros sitios: frena CSRF).
- En la base solo se guarda el hash del token de sesión.
- Todo acceso denegado queda en la auditoría.
"""
import os

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, User, UserSession, utcnow
from app.security import hash_token

COOKIE_NAME = "noc_session"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"   # poner COOKIE_SECURE=1 cuando haya HTTPS


def now_naive():
    """Hora UTC sin zona horaria (así la devuelve SQLite al leer)."""
    return utcnow().replace(tzinfo=None)


def auditar(db: Session, actor: str, accion: str, detalle: str, resultado: str = "OK"):
    """Registra una acción en la auditoría (quién, qué, cuándo, resultado)."""
    db.add(AuditLog(actor=(actor or "?")[:100], action=accion,
                    detail=(detalle or "")[:500], result=resultado))
    db.commit()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Devuelve el usuario de la sesión actual o responde 401."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    sesion = db.query(UserSession).filter(UserSession.token_hash == hash_token(token)).first()
    if not sesion or sesion.expires_at < now_naive():
        raise HTTPException(status_code=401, detail="Sesión vencida")
    user = db.query(User).filter(User.id == sesion.user_id).first()
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="Usuario no válido")
    return user


def require_roles(*roles):
    """Fabrica una dependencia que solo deja pasar a los roles indicados.

    Denegar por defecto: si el rol no está en la lista, responde 403 y audita.
    """
    def dependencia(request: Request,
                    user: User = Depends(current_user),
                    db: Session = Depends(get_db)) -> User:
        if user.role not in roles:
            auditar(db, user.username, "ACCESO_DENEGADO",
                    f"{request.method} {request.url.path} (rol {user.role})", "DENEGADO")
            raise HTTPException(status_code=403,
                                detail="Tu rol no tiene permiso para esta acción")
        return user
    return dependencia