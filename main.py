import os
import jwt
import datetime
from httpx import AsyncClient
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

app = FastAPI()
security = HTTPBearer()

# --- CONFIGURACIÓN SEGURA (Usa las variables de Render) ---
MONGO_URL = os.getenv("MONGO_URL")
TOKEN_APISPERU = os.getenv("TOKEN_APISPERU")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# --- SEGURIDAD JWT ---
def crear_token(data: dict):
    payload = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def obtener_usuario_actual(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except:
        raise HTTPException(status_code=401, detail="Sesión inválida")

# --- ENDPOINTS ---

@app.post("/login")
async def login(req: LoginRequest):
    user_db = await db.usuarios.find_one({"username": req.username})
    if not user_db or not pwd_context.verify(req.password, user_db["password"]):
        raise HTTPException(status_code=401, detail="Usuario o clave incorrectos")
    
    token = crear_token({"sub": user_db["username"], "role": user_db["role"]})
    return {"status": "ok", "token": token, "user": user_db["username"], "role": user_db["role"]}

@app.get("/consultar-dni/{dni}")
async def consultar_dni(dni: str, user=Depends(obtener_usuario_actual)):
    url = f"https://dniruc.apisperu.com/api/v1/dni/{dni}?token={TOKEN_APISPERU}"
    async with AsyncClient() as client_http:
        try:
            response = await client_http.get(url, timeout=15.0)
            return response.json()
        except:
            raise HTTPException(status_code=500, detail="Error de conexión con RENIEC")

@app.get("/verificar-visita/{dni}/{fecha}")
async def verificar_visita(dni: str, fecha: str, user=Depends(obtener_usuario_actual)):
    existe = await db.visitas.find_one({"dni": dni, "fecha": fecha})
    return {"existe": bool(existe)}

@app.post("/sincronizar")
async def sincronizar(visita: Visita, user=Depends(obtener_usuario_actual)):
    try:
        # 1. EL JUEZ FINAL: Revisamos si ya existe en la base de datos
        existe = await db.visitas.find_one({
            "dni": visita.dni, 
            "fecha": visita.fecha
        })
        
        if existe:
            # Si existe, el servidor responde con un error 400 (Bad Request)
            raise HTTPException(
                status_code=400, 
                detail=f"Error: El DNI {visita.dni} ya fue registrado el día {visita.fecha}"
            )

        # 2. Si no existe, procedemos a guardar
        data = visita.dict()
        data["promotor"] = user["sub"] 
        data["registro_servidor"] = datetime.datetime.now()
        
        await db.visitas.insert_one(data)
        return {"status": "ok", "message": "Visita sincronizada correctamente"}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error crítico en DB: {e}")
        raise HTTPException(status_code=500, detail="Error interno al procesar la visita")

@app.get("/reporte/{fecha}")
async def reporte(fecha: str, user=Depends(obtener_usuario_actual)):
    filtro = {"fecha": fecha}
    # Si no es supervisor, solo ve sus propias visitas
    if user["role"] != "supervisor":
        filtro["promotor"] = user["sub"]
        
    cursor = db.visitas.find(filtro)
    visitas = await cursor.to_list(length=1000)
    for v in visitas: v["_id"] = str(v["_id"])
    return visitas
