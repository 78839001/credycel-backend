import os
import jwt
import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

app = FastAPI()
security = HTTPBearer()

# --- CONFIGURACIÓN DE SEGURIDAD (Variables de Entorno) ---
# En Render, debes agregar estas 3 variables en 'Environment'
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://user:pass@cluster...")
TOKEN_APISPERU = os.getenv("TOKEN_APISPERU", "tu_token_aqui")
SECRET_KEY = os.getenv("SECRET_KEY", "una_clave_secreta_muy_larga_y_segura_2026")
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# CORS Protegido: Cambia '*' por la URL de tu app en producción (ej. Netlify/GitHub Pages)
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

# --- FUNCIONES DE SEGURIDAD ---
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
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

# --- ENDPOINTS ---

@app.post("/login")
async def login(req: LoginRequest):
    user_db = await db.usuarios.find_one({"username": req.username})
    if not user_db or not pwd_context.verify(req.password, user_db["password"]):
        raise HTTPException(status_code=401, detail="Acceso denegado")
    
    token = crear_token({"sub": user_db["username"], "role": user_db["role"]})
    return {"status": "ok", "token": token, "user": user_db["username"], "role": user_db["role"]}

@app.get("/consultar-dni/{dni}")
async def consultar_dni(dni: str, user=Depends(obtener_usuario_actual)):
    url = f"https://dniruc.apisperu.com/api/v1/dni/{dni}?token={TOKEN_APISPERU}"
    async with httpx.AsyncClient() as client_http:
        try:
            res = await client_http.get(url, timeout=10.0)
            return res.json()
        except:
            raise HTTPException(status_code=500, detail="Error DNI")

@app.get("/verificar-visita/{dni}/{fecha}")
async def verificar_visita(dni: str, fecha: str, user=Depends(obtener_usuario_actual)):
    existe = await db.visitas.find_one({"dni": dni, "fecha": fecha})
    return {"existe": bool(existe)}

@app.post("/sincronizar")
async def sincronizar(visita: Visita, user=Depends(obtener_usuario_actual)):
    data = visita.dict()
    # Forzamos que el promotor sea el usuario del token (Seguridad Nivel 4)
    data["promotor"] = user["sub"] 
    data["registro_servidor"] = datetime.datetime.now()
    await db.visitas.insert_one(data)
    return {"status": "ok"}

@app.get("/reporte/{fecha}")
async def reporte(fecha: str, user=Depends(obtener_usuario_actual)):
    # Solo el supervisor puede ver reportes globales
    filtro = {"fecha": fecha}
    if user["role"] != "supervisor":
        filtro["promotor"] = user["sub"]
        
    cursor = db.visitas.find(filtro)
    visitas = await cursor.to_list(length=1000)
    for v in visitas: v["_id"] = str(v["_id"])
    return visitas

@app.post("/crear-usuario")
async def crear_usuario(nuevo_user: User, admin=Depends(obtener_usuario_actual)):
    # Solo un supervisor puede crear otros usuarios
    if admin["role"] != "supervisor":
        raise HTTPException(status_code=403, detail="No tienes permisos")
        
    existe = await db.usuarios.find_one({"username": nuevo_user.username})
    if existe: raise HTTPException(status_code=400, detail="Ya existe")
    
    user_dict = {
        "username": nuevo_user.username,
        "password": pwd_context.hash(nuevo_user.password),
        "role": nuevo_user.role,
        "fecha_creacion": datetime.datetime.now()
    }
    await db.usuarios.insert_one(user_dict)
    return {"msg": "Usuario creado"}
