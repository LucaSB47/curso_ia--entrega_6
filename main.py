import os
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from state import AgentState
from agents.research_agent import nodo_investigador
from agents.analyst_agent import nodo_analista


# 1. Cargar entorno e instanciar LLM
load_dotenv()
llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)

MAX_PASOS = 6

# 2. Esquemas y Prompts
class DecisionSupervisor(BaseModel):
    next: Literal["investigador", "analista", "FINISH"] = Field(
        description="Próximo agente a invocar, o FINISH si la tarea ya está completa"
    )
    razon: str = Field(description="Breve justificación de la decisión")

SUPERVISOR_PROMPT = """Sos el Supervisor de un equipo con dos especialistas:
investigador: busca datos concretos en las políticas internas de TechCorp.
analista: hace cálculos matemáticos a partir de datos ya obtenidos.

Reglas:
1. Si falta un dato de la empresa, mandá a 'investigador'.
2. Si ya se buscó el dato pero falta calcular, mandá a 'analista'.
3. Si ya se buscó Y se calculó lo necesario, respondé 'FINISH'.
4. Nunca repitas el mismo agente dos veces seguidas si ya cumplió su parte.

Contribuciones hasta ahora:
{contribuciones}"""

llm_supervisor = llm.with_structured_output(DecisionSupervisor)

# 3. Nodos principales
def nodo_supervisor(state: AgentState) -> dict:
    if state.get("pasos", 0) >= MAX_PASOS:
        return {"next_agent": "FINISH", "task_completed": True}
    
    contribuciones_texto = "\n".join(
        f"- [{c['agente']}]: {c['aporte'][:200]}" for c in state.get("contribuciones", [])
    ) or "(ninguna todavía)"
    
    pregunta_original = state["messages"][0].content
    prompt_sistema = SUPERVISOR_PROMPT.format(contribuciones=contribuciones_texto)
    
    decision = llm_supervisor.invoke([
        {"role": "system", "content": prompt_sistema},
        {"role": "user", "content": f"Tarea original: {pregunta_original}"}
    ])
    
    return {"next_agent": decision.next, "task_completed": decision.next == "FINISH"}

def nodo_sintesis(state: AgentState) -> dict:
    contribuciones_texto = "\n".join(f"- [{c['agente']}] {c['aporte']}" for c in state.get("contribuciones", []))
    pregunta_original = state["messages"][0].content
    prompt = (
        f"Pregunta original: {pregunta_original}\n\n"
        f"Aportes del equipo:\n{contribuciones_texto}\n\n"
        "Redactá una respuesta final clara y breve combinando estos aportes."
    )
    respuesta_final = llm.invoke(prompt)
    return {"messages": [AIMessage(content=respuesta_final.content, name="supervisor")]}

def enrutar(state: AgentState) -> Literal["investigador", "analista", "sintesis"]:
    if state["next_agent"] == "FINISH":
        return "sintesis"
    return state["next_agent"]

# 4. Construcción del Grafo
grafo = StateGraph(AgentState)
grafo.add_node("supervisor", nodo_supervisor)
grafo.add_node("investigador", nodo_investigador)
grafo.add_node("analista", nodo_analista)
grafo.add_node("sintesis", nodo_sintesis)

grafo.add_edge(START, "supervisor")
grafo.add_conditional_edges("supervisor", enrutar, {
    "investigador": "investigador",
    "analista": "analista",
    "sintesis": "sintesis",
})
grafo.add_edge("investigador", "supervisor")
grafo.add_edge("analista", "supervisor")
grafo.add_edge("sintesis", END)

app = grafo.compile()

# 5. Script de Prueba (Graba la terminal corriendo esto)
if __name__ == "__main__":
    pregunta = (
        "Un empleado va a cumplir 12 años en TechCorp. Tuvo 14 días de vacaciones los primeros "
        "5 años, 21 los siguientes 5, y ahora tiene derecho a 28 días. ¿Cuántos días de vacaciones "
        "acumuló en total en esos 12 años?"
    )
    
    estado_inicial = {
        "messages": [HumanMessage(content=pregunta)],
        "next_agent": None,
        "contribuciones": [],
        "pasos": 0,
        "task_completed": False,
    }
    
    print("\n--- Iniciando Flujo de Delegación ---\n")
    for evento in app.stream(estado_inicial, stream_mode="updates"):
        for nodo, actualizacion in evento.items():
            print(f"📍 Nodo ejecutado: {nodo}")
            if "messages" in actualizacion:
                for m in actualizacion["messages"]:
                    print(f"[{m.name}] {m.content}\n")
                    
    print("-" * 40)
    resultado_final = app.invoke(estado_inicial)
    print("\nRESPUESTA FINAL (Síntesis):\n")
    print(resultado_final["messages"][-1].content)