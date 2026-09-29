import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import create_agent

# Cargar .env e instanciar modelo
load_dotenv()
llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)

# Base de datos simulada para la demostración
BASE_DE_DATOS = {
    "vacaciones": "Los empleados con menos de 5 años de antigüedad acceden a 14 días corridos de vacaciones. Los empleados con entre 5 y 10 años acceden a 21 días. Los empleados con más de 10 años acceden a 28 días.",
    "teletrabajo": "El esquema estándar es de 3 días de trabajo remoto y 2 días presenciales por semana.",
}

@tool
def buscar_en_politicas_internas(pregunta: str) -> str:
    """Busca información en las políticas internas de TechCorp (vacaciones, teletrabajo, etc.). 
    Usar para cualquier pregunta sobre reglas o números concretos de la empresa."""
    pregunta_lower = pregunta.lower()
    
    if "vacaciones" in pregunta_lower:
        return f"[Fuente: politica_vacaciones.txt] {BASE_DE_DATOS['vacaciones']}"
    elif "teletrabajo" in pregunta_lower or "remoto" in pregunta_lower:
        return f"[Fuente: politica_teletrabajo.txt] {BASE_DE_DATOS['teletrabajo']}"
        
    return "No se encontró información relevante en las políticas."

# Creación del Agente
agente_investigador = create_agent(
    model=llm,
    tools=[buscar_en_politicas_internas],
    system_prompt=(
        "Sos un agente de investigación. Tu única función es buscar datos concretos en "
        "las políticas internas de TechCorp usando tu herramienta. NO hagas cálculos. "
        "Respondé de forma breve con los datos encontrados y su fuente."
    )
)

def nodo_investigador(state) -> dict:
    tarea = state["messages"][-1].content
    resultado = agente_investigador.invoke({"messages": [HumanMessage(content=tarea)]})
    respuesta = resultado["messages"][-1].content
    return {
        "messages": [AIMessage(content=respuesta, name="investigador")],
        "contribuciones": [{"agente": "investigador", "aporte": respuesta}],
        "pasos": state.get("pasos", 0) + 1,
    }