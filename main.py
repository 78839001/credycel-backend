from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
import datetime
from typing import Optional

app = FastAPI()

# Seguridad para contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def inicio():
    return {
        "status": "online",
        "msg": "Servidor Credycel v.1 (Seguridad Activa)",
        "docs": "/docs"
    }

# CONEXIÓN MONGODB
MONGO_URL = "mongodb+srv://erojas21749_db_user:310y41b3rT0@cluster0.saivmal.mongodb.net/credycel_db?retryWrites=true&w=majority"
client = AsyncIOMotorClient(MONGO_URL)
db = client.credycel_db

# --- MODELOS ---
class User(BaseModel):
    username: str
    password: str
    role: str  # 'promotor' o 'supervisor'

class LoginRequest(BaseModel):
    username: str
    password: str

class Visita(BaseModel):
    dni: str
    nombre: str
    telefono: str
    score: int
    lat: float
    lon: float
    fecha: str
    promotor: str
    foto_base64: Optional[str] = None

# --- SEGURIDAD ---
def obtener_hash(password: str):
    return pwd_context.hash(password)

def verificar_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# --- ENDPOINTS ---

@app.post("/crear-usuario")
async def crear_usuario(user: User):
    # Validamos que el rol sea correcto
    if user.role not in ["promotor", "supervisor"]:
        raise HTTPException(status_code=400, detail="Rol no válido. Use 'promotor' o 'supervisor'")
    
    existe = await db.usuarios.find_one({"username": user.username})
    if existe:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    
    user_dict = {
        "username": user.username,
        "password": obtener_hash(user.password),
        "role": user.role,
        "fecha_creacion": datetime.datetime.now()
    }
    await db.usuarios.insert_one(user_dict)
    return {"msg": f"Usuario {user.username} creado como {user.role}"}

@app.post("/login")
async def login(req: LoginRequest):
    user_db = await db.usuarios.find_one({"username": req.username})
    if not user_db or not verificar_password(req.password, user_db["password"]):
        raise HTTPException(status_code=401, detail="Usuario o clave incorrectos")
    
    return {
        "status": "ok", 
        "user": user_db["username"], 
        "role": user_db["role"]
    }

@app.post("/sincronizar")
async def sincronizar_visita(visita: Visita):
    try:
        data = visita.dict()
        data["registro_servidor"] = datetime.datetime.now()
        await db.visitas.insert_one(data)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reporte/{fecha_consulta}")
async def obtener_reporte(fecha_consulta: str):
    cursor = db.visitas.find({"fecha": fecha_consulta})
    visitas = await cursor.to_list(length=1000)
    for v in visitas:
        v["_id"] = str(v["_id"])
    return visitas
