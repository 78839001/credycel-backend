from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

# Configuración de CORS para que el frontend (puerto 5500) pueda hablar con el backend (puerto 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelo de datos según tu boceto
class Visita(BaseModel):
    dni: str
    nombre: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    score: int

@app.get("/")
def inicio():
    return {"mensaje": "Servidor de Credycel Operativo"}

@app.post("/sincronizar")
async def recibir_visita(visita: Visita):
    print(f"✅ Registro recibido: {visita.nombre} (DNI: {visita.dni})")
    return {"status": "success", "mensaje": "Visita guardada en el servidor"}