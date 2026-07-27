import os
import glob
import pandas as pd
import streamlit as st

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from my_keys import GEMINI_API_KEY

os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

# Configuración de la página en Streamlit
st.set_page_config(
    page_title="CiberGuardIA - Asistente de Concientización",
    page_icon="🛡️",
    layout="centered"
)

# =====================================================================
# CARGA Y CREACIÓN DE VECTOR STORE (CACHEADO)
# =====================================================================
@st.cache_resource
def inicializar_motor_rag(directorio_data="data"):
    """Carga los CSVs y construye el vector store FAISS una sola vez en caché."""
    documentos = []
    archivos_csv = glob.glob(os.path.join(directorio_data, "*.csv"))

    for archivo in archivos_csv:
        try:
            df = pd.read_csv(archivo, encoding="utf-8", on_bad_lines="skip")
            for index, fila in df.iterrows():
                contenido_texto = " | ".join([f"{col}: {val}" for col, val in fila.items() if pd.notna(val)])
                doc = Document(
                    page_content=contenido_texto,
                    metadata={"fuente": os.path.basename(archivo), "fila": index}
                )
                documentos.append(doc)
        except Exception as e:
            st.error(f"Error al leer {archivo}: {e}")

    if not documentos:
        return None, 0

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs_divididos = text_splitter.split_documents(documentos)

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_store = FAISS.from_documents(docs_divididos, embeddings)
    retriever = vector_store.as_retriever(search_kwargs={"k": 3})

    # Configuración de la cadena RAG
    llm = ChatGoogleGenerativeAI(model="gemini-3-flash-preview", temperature=0.2)
    
    plantilla_prompt = """
Eres CiberGuardIA, un especialista y consultor educativo en concientización de Ciberseguridad.
Tu misión es ayudar a empleados y usuarios a reconocer amenazas digitales (phishing, ingeniería social, fugas de información),
explicar buenas prácticas digitales y guiar sobre las políticas internas de seguridad.

REGLAS DE RESPUESTA:
1. Responde de forma clara, didáctica y directa basándote ÚNICAMENTE en el siguiente contexto.
2. Si la consulta NO está respaldada por el contexto proporcionado, responde educadamente que no dispones de esa política o norma específica en tu base de datos y aconseja contactar al área de TI / Ciberseguridad.
3. Si el usuario te presenta un texto o correo sospechoso, analiza los indicadores de riesgo ("Red Flags") usando la información del contexto.
4. NUNCA entregues códigos maliciosos, scripts de exploit o instrucciones para realizar ataques. Tu enfoque es 100% defensivo.

Contexto disponible:
{context}

Pregunta del Usuario:
{question}

Respuesta del Agente CiberGuardIA:
"""
    prompt = ChatPromptTemplate.from_template(plantilla_prompt)

    def formatear_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    cadena_rag = (
        {"context": retriever | formatear_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    return cadena_rag, len(documentos)


# =====================================================================
# INTERFAZ GRÁFICA (STREAMLIT UI)
# =====================================================================
st.title("🛡️ CiberGuardIA")
st.caption("Asistente Virtual para la Concientización y Prevención en Ciberseguridad")

# Barra lateral informativa
with st.sidebar:
    st.header("📌 Estado del Agente")
    cadena_rag, total_docs = inicializar_motor_rag()
    
    if cadena_rag:
        st.success(f"Base de conocimientos cargada ({total_docs} registros).")
    else:
        st.error("No se encontraron documentos en la carpeta 'data/'.")
    
    st.markdown("---")
    st.subheader("💡 Consultas de ejemplo")
    st.markdown("- *'¿Qué hago si me roban la laptop?'*")
    st.markdown("- *'¿Cómo reconozco un correo de phishing?'*")
    st.markdown("- *'Me llegó un SMS urgente para pagar una multa, ¿es real?'*")

# Inicialización de historial de chat
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "¡Hola! Soy CiberGuardIA. ¿Tienes dudas sobre buenas prácticas de seguridad o deseas analizar un mensaje sospechoso?"}
    ]

# Mostrar mensajes anteriores
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# Capturar entrada del usuario
if prompt_usuario := st.chat_input("Escribe tu duda o pega un texto sospechoso aquí..."):
    if not cadena_rag:
        st.error("El motor RAG no está listo. Revisa la base de conocimientos.")
        st.stop()

    # Agregar y mostrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt_usuario})
    st.chat_message("user").write(prompt_usuario)

    # Generar respuesta con Gemini + RAG
    with st.chat_message("assistant"):
        with st.spinner("Analizando base de datos y políticas de seguridad..."):
            respuesta = cadena_rag.invoke(prompt_usuario)
            st.write(respuesta)

    # Guardar respuesta en el historial
    st.session_state.messages.append({"role": "assistant", "content": respuesta})