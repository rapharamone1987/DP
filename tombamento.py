import streamlit as st
from groq import Groq
import pdfplumber
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import time
import io
import base64
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

def ocr_groq_vision(foto_bytes, instrucao):
    """Usa o modelo Vision do Groq para ler a placa/serial"""
    try:
        base64_image = encode_image(foto_bytes)
        completion = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Extraia apenas o valor de: {instrucao}. Responda apenas o número ou texto puro."},
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
st.set_page_config(page_title="Tombamento Groq", layout="centered")

if "bens_lista" not in st.session_state: st.session_state.bens_lista = []
if "inventario" not in st.session_state: st.session_state.inventario = {}
if "idx_atual" not in st.session_state: st.session_state.idx_atual = 0
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None 

st.markdown("""<style>
    .barra { background-color: #1E461E; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
</style>""", unsafe_allow_html=True)

st.title("🛡️ Tombamento Digital (Groq)")

# --- 4. TELA DE CARGA ---
if not st.session_state.bens_lista:
    st.subheader("Carregar Relação de Bens")
    tab1, tab2, tab3 = st.tabs(["📄 Analisar PDF", "📊 Colar Excel", "📝 Manual"])
    
    with tab1:
        pdf_file = st.file_uploader("Suba o PDF", type="pdf")
        if pdf_file and st.button("🔍 Extrair Lista (Groq)"):
            with st.spinner("Analisando PDF..."):
                texto = extrair_texto_pdf(pdf_file)
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": f"Liste apenas os nomes dos bens para tombamento contidos neste texto, um por linha:\n{texto}"}]
                )
                itens = [l.strip("- *") for l in completion.choices[0].message.content.split('\n') if len(l.strip()) > 3]
                st.session_state.bens_lista = [{"nome": i} for i in itens]
                st.rerun()

    with tab2:
        csv_in = st.text_area("Cole colunas do Excel:")
        if st.button("Carregar Planilha"):
            df = pd.read_csv(io.StringIO(csv_in), sep=None, engine='python', header=None)
            st.session_state.bens_lista = [{"nome": str(row[0])} for _, row in df.iterrows()]
            st.rerun()

    with tab3:
        txt_in = st.text_area("Um item por linha:")
        if st.button("Carregar Lista"):
            st.session_state.bens_lista = [{"nome": l.strip()} for l in txt_in.split('\n') if l.strip()]
            st.rerun()

# --- 5. EXECUÇÃO DO TOMBAMENTO ---
elif st.session_state.bens_lista and not st.session_state.get("concluido"):
    idx = st.session_state.idx_atual
    item = st.session_state.bens_lista[idx]
    
    st.markdown(f'<div class="barra">ITEM {idx + 1} de {len(st.session_state.bens_lista)}</div>', unsafe_allow_html=True)
    st.subheader(item["nome"])
    
    if idx not in st.session_state.inventario:
        st.session_state.inventario[idx] = {"placa": "", "serial": "", "f_fixa": None, "f_geral": None}
    
    inv = st.session_state.inventario[idx]

    # --- CAMPO 1: PATRIMÔNIO (SCANNER VISION) ---
    with st.container(border=True):
        st.write("🔍 **1. Nº de Patrimônio (Plaqueta)**")
        if st.session_state.camera_ativa == f"scan_p_{idx}":
            f_p = st.camera_input("Foque na Plaqueta", key=f"cp_{idx}")
            if f_p:
                with st.spinner("Groq Vision lendo..."):
                    inv["placa"] = ocr_groq_vision(f_p.getvalue(), "número do patrimônio/plaqueta")
                st.session_state.camera_ativa = None; st.rerun()
        else:
            col1, col2 = st.columns([0.7, 0.3])
            inv["placa"] = col1.text_input("Número da Placa:", value=inv["placa"], key=f"in_p_{idx}")
            if col2.button("📷 Scan", key=f"btn_p_{idx}"):
                st.session_state.camera_ativa = f"scan_p_{idx}"; st.rerun()

    # --- CAMPO 2: SERIAL (SCANNER VISION) ---
    with st.container(border=True):
        st.write("🔍 **2. Número de Série (Fabricante)**")
        if st.session_state.camera_ativa == f"scan_s_{idx}":
            f_s = st.camera_input("Foque no Serial", key=f"cs_{idx}")
            if f_s:
                with st.spinner("Groq Vision lendo..."):
                    inv["serial"] = ocr_groq_vision(f_s.getvalue(), "número de série (S/N)")
                st.session_state.camera_ativa = None; st.rerun()
        else:
            col1, col2 = st.columns([0.7, 0.3])
            inv["serial"] = col1.text_input("Nº de Série:", value=inv["serial"], key=f"in_s_{idx}")
            if col2.button("📷 Scan ", key=f"btn_s_{idx}"):
                st.session_state.camera_ativa = f"scan_serial_{idx}"; st.rerun()

    # --- FOTOS DE COMPROVAÇÃO ---
    st.write("### 📸 Fotos de Comprovação")
    c1, c2 = st.columns(2)
    with c1:
        if inv["f_fixa"] is None:
            if st.session_state.camera_ativa == f"f1_{idx}":
                f1 = st.camera_input("Foto Etiqueta Colada", key=f"cam1_{idx}")
                if f1: inv["f_fixa"] = f1; st.session_state.camera_ativa = None; st.rerun()
            elif st.button("📷 Plaqueta Colada"): st.session_state.camera_ativa = f"f1_{idx}"; st.rerun()
        else:
            st.image(inv["f_fixa"], width=150)
            if st.button("🔄 Refazer 1", key=f"r1_{idx}"): inv["f_fixa"] = None; st.rerun()

    with c2:
        if inv["f_geral"] is None:
            if st.session_state.camera_ativa == f"f2_{idx}":
                f2 = st.camera_input("Foto do Bem", key=f"cam2_{idx}")
                if f2: inv["f_geral"] = f2; st.session_state.camera_ativa = None; st.rerun()
            elif st.button("📷 Bem Geral"): st.session_state.camera_ativa = f"f2_{idx}"; st.rerun()
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
    servidor = st.text_input("Nome do Servidor Responsável:")
    if st.button("🚀 GERAR PDF"):
        pdf = FPDF(); pdf.set_margins(15, 15, 15)
        for i, it in enumerate(st.session_state.bens_lista):
            pdf.add_page()
            res = st.session_state.inventario[i]
            pdf.set_font("Arial", 'B', 16); pdf.cell(180, 10, tr("TERMO DE TOMBAMENTO"), ln=True, align='C')
            pdf.set_fill_color(240); pdf.set_font("Arial", 'B', 11)
            pdf.cell(180, 10, tr(f" ITEM: {it['nome'].upper()}"), border=1, ln=True, fill=True)
            pdf.cell(90, 10, tr(f" PATRIMONIO: {res['placa']}"), border=1)
            pdf.cell(90, 10, tr(f" SERIE: {res['serial']}"), border=1, ln=True)
            
            curr_y = pdf.get_y() + 10
            if res["f_fixa"]:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t1:
                    t1.write(res["f_fixa"].getvalue())
                    pdf.image(t1.name, x=20, y=curr_y, w=80)
            if res["f_geral"]:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t2:
                    t2.write(res["f_geral"].getvalue())
                    pdf.image(t2.name, x=105, y=curr_y, w=85)
        
        st.download_button("📥 Baixar PDF", data=pdf.output(dest='S'), file_name="Tombamento.pdf")

if st.sidebar.button("Reiniciar"):
    st.session_state.clear(); st.rerun()
