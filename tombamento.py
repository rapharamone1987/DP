import streamlit as st
from groq import Groq
import pdfplumber
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import io
import base64
import time
from PIL import Image

# --- 1. CONFIGURAÇÃO DO CLIENTE GROQ ---
if "GROQ_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GROQ_API_KEY"]
else:
    CHAVE_API = ""

client = None
if CHAVE_API:
    client = Groq(api_key=CHAVE_API)

# --- 2. FUNÇÕES DE APOIO ---
def tr(texto):
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def extrair_texto_pdf(pdf_file):
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto += pagina.extract_text() + "\n"
    return texto

def encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')

def scanner_ia_groq(foto_bytes, instrucao):
    """Usa o Llama Vision do Groq para ler o Código de Barras ou Serial"""
    try:
        base64_image = encode_image(foto_bytes)
        completion = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Atue como um leitor de código de barras e etiquetas. {instrucao}. Responda apenas o código puro, sem texto extra."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            temperature=0.1
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"Erro: {e}"

# --- 3. INTERFACE E ESTADO ---
st.set_page_config(page_title="Tombamento Groq Vision", layout="centered")

if "bens_lista" not in st.session_state: st.session_state.bens_lista = []
if "inventario" not in st.session_state: st.session_state.inventario = {}
if "idx_atual" not in st.session_state: st.session_state.idx_atual = 0
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.markdown("""<style>
    .barra { background-color: #003366; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; font-weight: bold; }
</style>""", unsafe_allow_html=True)

st.title("🛡️ Tombamento com Groq Vision")

# --- 4. TELA DE CARGA ---
if not st.session_state.bens_lista:
    st.subheader("Carga da Relação de Bens")
    tab1, tab2 = st.tabs(["📊 Colar Excel", "📄 Analisar PDF"])
    
    with tab1:
        csv_in = st.text_area("Cole aqui as colunas da sua planilha:")
        if st.button("Carregar Lista da Planilha"):
            df = pd.read_csv(io.StringIO(csv_in), sep=None, engine='python', header=None)
            st.session_state.bens_lista = [{"nome": str(row[0])} for _, row in df.iterrows()]
            st.rerun()

    with tab2:
        pdf_file = st.file_uploader("Suba o PDF do TR ou Empenho", type="pdf")
        if pdf_file and client:
            if st.button("🔍 Extrair Lista com Groq"):
                with st.spinner("Lendo PDF..."):
                    texto_pdf = extrair_texto_pdf(pdf_file)
                    completion = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": f"Liste apenas os nomes dos bens deste texto, um por linha:\n{texto_pdf}"}]
                    )
                    itens = [l.strip("- *") for l in completion.choices[0].message.content.split('\n') if len(l.strip()) > 3]
                    st.session_state.bens_lista = [{"nome": i} for i in itens]
                    st.rerun()

# --- 5. EXECUÇÃO COM SCANNER ---
elif st.session_state.bens_lista and not st.session_state.get("concluido"):
    idx = st.session_state.idx_atual
    item = st.session_state.bens_lista[idx]
    
    st.markdown(f'<div class="barra">ITEM {idx + 1} de {len(st.session_state.bens_lista)}</div>', unsafe_allow_html=True)
    st.subheader(item["nome"])
    
    if idx not in st.session_state.inventario:
        st.session_state.inventario[idx] = {"placa": "", "serial": "", "f_fixa": None, "f_geral": None}
    
    inv = st.session_state.inventario[idx]

    # --- CAMPO 1: PLAQUETA (SCANNER) ---
    with st.container(border=True):
        st.write("🎯 **1. Plaqueta de Patrimônio**")
        if st.session_state.camera_ativa == f"scan_p_{idx}":
            f_p = st.camera_input("Foque no Código de Barras", key=f"cp_{idx}")
            if f_p:
                with st.spinner("IA Groq decodificando barras..."):
                    inv["placa"] = scanner_ia_groq(f_p.getvalue(), "Extraia o número do código de barras ou o número da plaqueta de patrimônio")
                st.session_state.camera_ativa = None; st.rerun()
        else:
            c1, c2 = st.columns([0.7, 0.3])
            inv["placa"] = c1.text_input("Número:", value=inv["placa"], key=f"in_p_{idx}")
            if c2.button("📷 Scan", key=f"btn_p_{idx}"):
                st.session_state.camera_ativa = f"scan_p_{idx}"; st.rerun()

    # --- CAMPO 2: SERIAL (SCANNER) ---
    with st.container(border=True):
        st.write("🔍 **2. Número de Série (S/N)**")
        if st.session_state.camera_ativa == f"scan_s_{idx}":
            f_s = st.camera_input("Foque no Serial do Fabricante", key=f"cs_{idx}")
            if f_s:
                with st.spinner("IA Groq extraindo serial..."):
                    inv["serial"] = scanner_ia_groq(f_s.getvalue(), "Extraia o número de série (S/N, Serial Number)")
                st.session_state.camera_ativa = None; st.rerun()
        else:
            c3, c4 = st.columns([0.7, 0.3])
            inv["serial"] = c3.text_input("S/N:", value=inv["serial"], key=f"in_s_{idx}")
            if c4.button("📷 Scan ", key=f"btn_s_{idx}"):
                st.session_state.camera_ativa = f"scan_serial_{idx}"; st.rerun()

    # --- FOTOS DE PROVA ---
    st.write("### 📸 Registro de Fotos")
    col1, col2 = st.columns(2)
    with col1:
        if inv["f_fixa"] is None:
            if st.session_state.camera_ativa == f"f1_{idx}":
                f1 = st.camera_input("Foto Etiqueta Colada", key=f"cam1_{idx}")
                if f1: inv["f_fixa"] = f1; st.session_state.camera_ativa = None; st.rerun()
            elif st.button("📷 Foto Fixação"): st.session_state.camera_ativa = f"f1_{idx}"; st.rerun()
        else:
            st.image(inv["f_fixa"], width=150)
            if st.button("🔄 Refazer 1", key=f"r1_{idx}"): inv["f_fixa"] = None; st.rerun()

    with col2:
        if inv["f_geral"] is None:
            if st.session_state.camera_ativa == f"f2_{idx}":
                f2 = st.camera_input("Foto Geral do Bem", key=f"cam2_{idx}")
                if f2: inv["f_geral"] = f2; st.session_state.camera_ativa = None; st.rerun()
            elif st.button("📷 Foto Geral"): st.session_state.camera_ativa = f"f2_{idx}"; st.rerun()
        else:
            st.image(inv["f_geral"], width=150)
            if st.button("🔄 Refazer 2", key=f"r2_{idx}"): inv["f_geral"] = None; st.rerun()

    st.divider()
    if st.button("Próximo Item ➡️"):
        st.session_state.idx_atual += 1
        if st.session_state.idx_atual >= len(st.session_state.bens_lista):
            st.session_state.concluido = True
        st.rerun()

# --- 6. PDF FINAL ---
elif st.session_state.get("concluido"):
    st.balloons()
    servidor = st.text_input("Servidor Responsável:")
    if st.button("🚀 GERAR PDF"):
        try:
            pdf = FPDF(); pdf.set_margins(15, 15, 15)
            for i, it in enumerate(st.session_state.bens_lista):
                pdf.add_page()
                res = st.session_state.inventario[i]
                pdf.set_font("Arial", 'B', 16); pdf.set_text_color(0, 51, 102)
                pdf.cell(180, 10, tr("TERMO DE TOMBAMENTO"), ln=True, align='C')
                pdf.set_fill_color(240); pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0)
                pdf.cell(180, 10, tr(f" ITEM: {it['nome'].upper()}"), border=1, ln=True, fill=True)
                pdf.cell(90, 10, tr(f" PATRIMÔNIO: {res['placa']}"), border=1)
                pdf.cell(90, 10, tr(f" SÉRIE: {res['serial']}"), border=1, ln=True)
                
                curr_y = pdf.get_y() + 10
                if res["f_fixa"]:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t1:
                        t1.write(res["f_fixa"].getvalue())
                        pdf.image(t1.name, x=15, y=curr_y, w=85)
                if res["f_geral"]:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t2:
                        t2.write(res["f_geral"].getvalue())
                        pdf.image(t2.name, x=105, y=curr_y, w=85)
            
            st.download_button("📥 Baixar PDF", data=pdf.output(dest='S'), file_name="Tombamento.pdf")
        except Exception as e: st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Novo Tombamento"):
    st.session_state.clear(); st.rerun()
