import os
import glob
import pandas as pd

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from my_keys import GEMINI_API_KEY

# Configuración de clave de API para Gemini
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY


# =====================================================================
# 1. CARGA Y PROCESAMIENTO DE ARCHIVOS CSV (BASE DE CONOCIMIENTOS)
# =====================================================================
def cargar_documentos_ciberseguridad(directorio_data="data"):
    """Carga todos los archivos CSV del directorio data y los convierte en objetos Document."""
    documentos = []
    archivos_csv = glob.glob(os.path.join(directorio_data, "*.csv"))

    if not archivos_csv:
        print(f"⚠️ No se encontraron archivos CSV en el directorio '{directorio_data}'.")
        return documentos

    for archivo in archivos_csv:
        print(f"Procesando {os.path.basename(archivo)}...")
        try:
            # Se agrega encoding utf-8 u opcional on_bad_lines para omitir o ajustar filas con formato ambiguo
            df = pd.read_csv(
                archivo, 
                encoding="utf-8", 
                on_bad_lines="skip"  # Salta líneas mal formateadas sin tumbar la aplicación
            )
        except Exception as e:
            print(f"⚠️ Error al leer {archivo}: {e}")
            continue

        # Convertir cada fila del CSV en un documento
        for index, fila in df.iterrows():
            contenido_texto = " | ".join([f"{col}: {val}" for col, val in fila.items() if pd.notna(val)])
            
            doc = Document(
                page_content=contenido_texto,
                metadata={"fuente": os.path.basename(archivo), "fila": index}
            )
            documentos.append(doc)

    print(f"Total de registros cargados y convertidos en documentos: {len(documentos)}")
    return documentos


# =====================================================================
# 2. CREACIÓN DEL MOTOR DE BÚSQUEDA VECTORIAL (FAISS + EMBEDDINGS LOCALES)
# =====================================================================
def crear_vector_store(documentos):
    """Divide los documentos e indexa sus vectores en una base FAISS local."""
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs_divididos = text_splitter.split_documents(documentos)

    # Embeddings 100% locales (sin consumo de API de terceros para la vectorización)
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    # Creación del almacenamiento vectorial FAISS en memoria
    vector_store = FAISS.from_documents(docs_divididos, embeddings)
    
    # Recupera los 3 fragmentos de mayor similitud semántica
    return vector_store.as_retriever(search_kwargs={"k": 3})


# =====================================================================
# 3. CONSTRUCCIÓN DE LA CADENA RAG Y PROMPT DEL AGENTE
# =====================================================================
def obtener_cadena_rag(retriever):
    """Configura el modelo LLM Gemini y el prompt defensivo de ciberseguridad."""
    #llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2)
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

    # Función auxiliar para formatear los documentos recuperados
    def formatear_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    # Pipeline RAG
    cadena_rag = (
        {"context": retriever | formatear_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    return cadena_rag


# =====================================================================
# 4. INTERFAZ DE CONSOLA (CLI)
# =====================================================================
def ejecutar_agente():
    print("Iniciando Agente de Concientización en Ciberseguridad (CiberGuardIA)...")
    
    docs = cargar_documentos_ciberseguridad()
    if not docs:
        print("Error: No hay información en la base de conocimientos. Revisa la carpeta 'data/'.")
        return

    retriever = crear_vector_store(docs)
    cadena_rag = obtener_cadena_rag(retriever)

    print("\n¡CiberGuardIA está en línea! Consulta sobre políticas, alertas de phishing o buenas prácticas.")
    print("Escribe 'salir' para terminar la sesión.\n")

    while True:
        try:
            pregunta = input("\nUsuario: ")
            if pregunta.strip().lower() in ["salir", "exit", "quit"]:
                print("\nCiberGuardIA: ¡Mantén tus credenciales seguras! Hasta luego.")
                break

            if not pregunta.strip():
                continue

            respuesta = cadena_rag.invoke(pregunta)
            print(f"\nCiberGuardIA: {respuesta}")
            print("-" * 60)

        except KeyboardInterrupt:
            print("\nSesión finalizada.")
            break


if __name__ == "__main__":
    ejecutar_agente()