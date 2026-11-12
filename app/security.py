"""Contraseñas y tokens de sesión. Solo biblioteca estándar.

- La contraseña nunca se guarda: se guarda un hash scrypt con sal aleatoria.
- El token de sesión se entrega al navegador; en la base solo queda su hash SHA-256.
"""
import hashlib
import hmac
import os
import secrets

ROLES = ("admin", "operador", "auditor")

# Parámetros de scrypt (costo de memoria y CPU para frenar la fuerza bruta)
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    """Devuelve 'scrypt$N$r$p$sal$hash' (todo en hexadecimal)."""
    sal = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${sal.hex()}${dk.hex()}"


def verify_password(password: str, guardado: str) -> bool:
    """Compara en tiempo constante. Cualquier formato raro devuelve False."""
    try:
        _, n, r, p, sal_hex, hash_hex = guardado.split("$")
        dk = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(sal_hex),
                            n=int(n), r=int(r), p=int(p), dklen=len(hash_hex) // 2)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


def new_token() -> str:
    """Token aleatorio e impredecible para la cookie de sesión."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()