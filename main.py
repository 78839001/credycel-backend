from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
import datetime
import httpx
from typing import Optional

app = FastAPI()

# Configuración de seguridad (Hasheo de claves)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN DE CONEXIONES ---
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

# --- ENDPOINTS ---

@app.get("/")
def inicio():
    return {"status": "online", "msg": "Credycel Backend v.2.1 Ready"}

@app.post("/login")
async def login(req: LoginRequest):
    user_db = await db.usuarios.find_one({"username": req.username})
    if not user_db or not pwd_context.verify(req.password, user_db["password"]):
        raise HTTPException(status_code=401, detail="Usuario o clave incorrectos")
    return {"status": "ok", "user": user_db["username"], "role": user_db["role"]}

@app.get("/consultar-dni/{dni}")
async def consultar_dni(dni: str):
    if len(dni) != 8:
        raise HTTPException(status_code=400, detail="DNI inválido")
    
    url = f"https://dniruc.apisperu.com/api/v1/dni/{dni}?token={TOKEN_APISPERU}"
    async with httpx.AsyncClient() as client_http:
        try:
            response = await client_http.get(url, timeout=10.0)
            return response.json()
        except:
            raise HTTPException(status_code=500, detail="Error de conexión con RENIEC")

# --- NUEVO: VERIFICAR DUPLICADOS EN LA NUBE ---
@app.get("/verificar-visita/{dni}/{fecha}")
async def verificar_visita(dni: str, fecha: str):
    # Busca en MongoDB si ya hay una visita con ese DNI en esa fecha
    existe = await db.visitas.find_one({"dni": dni, "fecha": fecha})
    if existe:
        return {"existe": True}
    return {"existe": False}

@app.post("/sincronizar")
async def sincronizar(visita: Visita):
    try:
        data = visita.dict()
        data["registro_servidor"] = datetime.datetime.now()
        await db.visitas.insert_one(data)
        return {"status": "ok"}
    except Exception as e:
        print(f"Error en DB: {e}")
        raise HTTPException(status_code=500, detail="Error al guardar registro")

@app.get("/reporte/{fecha}")
async def reporte(fecha: str):
    cursor = db.visitas.find({"fecha": fecha})
    visitas = await cursor.to_list(length=1000)
    for v in visitas: v["_id"] = str(v["_id"])
    return visitas

@app.post("/crear-usuario")
async def crear_usuario(user: User):
    existe = await db.usuarios.find_one({"username": user.username})
    if existe: raise HTTPException(status_code=400, detail="El usuario ya existe")
    user_dict = {
        "username": user.username,
        "password": pwd_context.hash(user.password),
        "role": user.role,
        "fecha_creacion": datetime.datetime.now()
    }
    await db.usuarios.insert_one(user_dict)
    return {"msg": "Usuario creado con éxito"}
