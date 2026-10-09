import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Base de datos SQLite guardada localmente
SQLALCHEMY_DATABASE_URL = "sqlite:///./noc_syslog.db"

# connect_args es necesario para SQLite en FastAPI para permitir múltiples hilos
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base para la creación de los modelos ORM
Base = declarative_base()

def get_db():
    """Generador de sesiones de base de datos para inyección de dependencias."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()