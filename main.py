from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import datetime
from typing import Optional

app = FastAPI()

# Permite que tu celular se conecte al servidor sin bloqueos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONEXIÓN A TU BASE DE DATOS MONGODB ---
# Usamos tu URL real con el usuario y contraseña que configuramos
MONGO_URL = "mongodb+srv://erojas21749_db_user:310y41b3rT0@cluster0.saivmal.mongodb.net/credycel_db?retryWrites=true&w=majority"
client = AsyncIOMotorClient(MONGO_URL)
db = client.credycel_db

# Modelo de datos: Debe coincidir exactamente con lo que envía el JS
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

@app.get("/")
def inicio():
    return {"status": "online", "msg": "Servidor Credycel v.1 Funcionando"}

@app.post("/sincronizar")
async def sincronizar_visita(visita: Visita):
    try:
        # Convertimos los datos a un formato que MongoDB entienda (Diccionario)
        data = visita.dict()
        
        # Agregamos la hora exacta en la que llegó al servidor
        data["registro_servidor"] = datetime.datetime.now()
        
        # Guardamos en la colección 'visitas'
        resultado = await db.visitas.insert_one(data)
        
        print(f"✅ Visita de {visita.nombre} guardada correctamente.")
        return {"status": "ok", "id_nube": str(resultado.inserted_id)}
        
    except Exception as e:
        print(f"❌ Error al guardar: {e}")
        raise HTTPException(status_code=500, detail="Error interno en la base de datos")

# Este endpoint te servirá para que luego tú veas los reportes por fecha
@app.get("/reporte/{fecha_consulta}")
async def obtener_reporte(fecha_consulta: str):
    # Ejemplo de consulta: https://tu-link.render.com/reporte/2026-04-12
    cursor = db.visitas.find({"fecha": fecha_consulta})
    visitas = await cursor.to_list(length=1000)
    
    # Convertimos los IDs de MongoDB a texto para que sean legibles
    for v in visitas:
        v["_id"] = str(v["_id"])
        
    return visitas
