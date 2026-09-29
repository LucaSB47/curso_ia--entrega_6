import os
import ast
import operator as op
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import create_agent

# Cargar .env e instanciar modelo
load_dotenv()
llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)

# Lógica de la calculadora segura
_OPERADORES = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg,
}

def _evaluar_nodo(nodo):
    if isinstance(nodo, ast.Constant):
        return nodo.value
    if isinstance(nodo, ast.BinOp):
        return _OPERADORES[type(nodo.op)](_evaluar_nodo(nodo.left), _evaluar_nodo(nodo.right))
    if isinstance(nodo, ast.UnaryOp):
        return _OPERADORES[type(nodo.op)](_evaluar_nodo(nodo.operand))
    raise ValueError("Expresión no permitida")

@tool
def calculadora(expresion: str) -> str:
    """Evalúa una expresión matemática (+, -, *, /, **, paréntesis). Ejemplo: '5*14+ 5*21 + 2*28'."""
    try:
        resultado = _evaluar_nodo(ast.parse(expresion, mode="eval").body)
        return f"Resultado: {resultado}"
    except Exception as e:
        return f"Error al calcular '{expresion}': {e}"

# Creación del Agente
agente_analista = create_agent(
    model=llm,
    tools=[calculadora],
    system_prompt=(
        "Sos un agente de análisis matemático. Tu única función es calcular usando tu "
        "herramienta a partir de los números que te den. NO busques información nueva."
    )
)

def nodo_analista(state) -> dict:
    tarea = state["messages"][-1].content
    resultado = agente_analista.invoke({"messages": [HumanMessage(content=tarea)]})
    respuesta = resultado["messages"][-1].content
    return {
        "messages": [AIMessage(content=respuesta, name="analista")],
        "contribuciones": [{"agente": "analista", "aporte": respuesta}],
        "pasos": state.get("pasos", 0) + 1,
    }