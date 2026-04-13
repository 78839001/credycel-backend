from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
import datetime
import httpx
from typing import Optional

app = FastAPI()

# Configuración de seguridad
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN PRIVADA ---
MONGO_URL = "mongodb+srv://erojas21749_db_user:310y41b3rT0@cluster0.saivmal.mongodb.net/credycel_db?retryWrites=true&w=majority"
TOKEN_APISPERU = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6ImVyb2phczIxNzQ5QG91dGxvb2suY29tIn0.E10BDz6gzUn6gjX781q7EFsKYeZF22rPWy6o_B2a-Kk"

client = AsyncIOMotorClient(MONGO_URL)
db = client.credycel_db

# --- MODELOS ---
class User(BaseModel):
    username: str
    password: str
    role: str

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

@app.get("/")
def inicio():
    return {"status": "online", "msg": "Credycel Secure Server v.2"}

@app.post("/crear-usuario")
async def crear_usuario(user: User):
    if user.role not in ["promotor", "supervisor"]:
        raise HTTPException(status_code=400, detail="Rol inválido")
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
    return {"msg": "Usuario creado"}

@app.post("/login")
async def login(req: LoginRequest):
    user_db = await db.usuarios.find_one({"username": req.username})
    if not user_db or not verificar_password(req.password, user_db["password"]):
        raise HTTPException(status_code=401, detail="Error de acceso")
    return {"status": "ok", "user": user_db["username"], "role": user_db["role"]}

# PROXY PARA DNI (Oculta el token)
@app.get("/consultar-dni/{dni}")
async def consultar_dni(dni: str):
    if len(dni) != 8:
        raise HTTPException(status_code=400, detail="DNI debe tener 8 cifras")
    
    url = f"https://dniruc.apisperu.com/api/v1/dni/{dni}?token={TOKEN_APISPERU}"
    async with httpx.AsyncClient() as client_http:
        try:
            response = await client_http.get(url, timeout=10.0)
            return response.json()
        except:
            raise HTTPException(status_code=500, detail="Error en servicio DNI")

@app.post("/sincronizar")
async def sincronizar(visita: Visita):
    data = visita.dict()
    data["registro_servidor"] = datetime.datetime.now()
    await db.visitas.insert_one(data)
    return {"status": "ok"}

@app.get("/reporte/{fecha}")
async def reporte(fecha: str):
    cursor = db.visitas.find({"fecha": fecha})
    visitas = await cursor.to_list(length=500)
    for v in visitas: v["_id"] = str(v["_id"])
    return visitas
