import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import json
import time
import pandas as pd
import io
from PIL import Image

# --- 1. CONFIGURAÇÃO DA IA ---
if "GOOGLE_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GOOGLE_API_KEY"]
else:
    CHAVE_API = "" 

@st.cache_resource
def inicializar_ia(api_key):
    try:
        genai.configure(api_key=api_key.strip())
        return genai.GenerativeModel(model_name='gemini-1.5-flash')
    except: return None

model = inicializar_ia(CHAVE_API)

# --- 2. FUNÇÕES DE APOIO ---
def ocr_etiqueta(foto_bytes, tipo_dado):
    try:
        img = Image.open(foto_bytes)
        prompt = f"Leia esta imagem e extraia apenas o {tipo_dado}. Responda apenas com os números ou letras encontrados, sem frases."
        res = model.generate_content([prompt, img])
        return res.text.strip()
    except Exception as e:
        return f"Erro: {e}"

def tr(texto):
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

# --- 3. INTERFACE E ESTADO ---
st.set_page_config(page_title="Tombamento com Scanner", layout="centered")

if "bens_lista" not in st.session_state: st.session_state.bens_lista = []
if "inventario" not in st.session_state: st.session_state.inventario = {}
if "idx_atual" not in st.session_state: st.session_state.idx_atual = 0
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None 

st.markdown("""<style>
    .barra { background-color: #004d00; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
</style>""", unsafe_allow_html=True)

st.title("🛡️ Tombamento com Scanner IA")

# --- 4. TELA DE CARGA (COM O BOTÃO DE PDF) ---
if not st.session_state.bens_lista:
    st.subheader("Carregar Relação de Bens")
    # ADICIONADA A ABA DE PDF ABAIXO
    tab1, tab2, tab3 = st.tabs(["📄 Analisar PDF (IA)", "📊 Colar Excel", "📝 Lista Manual"])
    
    with tab1:
        pdf_file = st.file_uploader("Suba o PDF do TR ou Empenho", type="pdf")
        if pdf_file:
            if st.button("🔍 Extrair Lista com IA"):
                with st.spinner("IA extraindo lista de bens..."):
                    try:
                        # Comando para extrair apenas a lista de nomes
                        prompt = "Liste apenas os nomes dos bens (produtos) contidos neste documento para tombamento, um por linha. Não escreva mais nada."
                        res = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_file.read()}, prompt])
                        itens = [l.strip("- *") for l in res.text.split('\n') if len(l.strip()) > 3]
                        if itens:
                            st.session_state.bens_lista = [{"nome": i} for i in itens]
                            st.rerun()
                        else:
                            st.error("IA não encontrou itens no PDF.")
                    except Exception as e:
                        st.error(f"Erro na IA: {e}")

    with tab2:
        csv_in = st.text_area("Cole as colunas da planilha (Excel):")
        if st.button("Carregar Planilha"):
            try:
                df = pd.read_csv(io.StringIO(csv_in), sep=None, engine='python')
                st.session_state.bens_lista = [{"nome": str(row[0])} for _, row in df.iterrows()]
                st.rerun()
            except: st.error("Erro no formato da planilha.")

    with tab3:
        txt_in = st.text_area("Um item por linha:")
        if st.button("Carregar Lista Manual"):
            st.session_state.bens_lista = [{"nome": l.strip()} for l in txt_in.split('\n') if l.strip()]
            st.rerun()

# --- 5. EXECUÇÃO COM SCANNER (DAQUI EM DIANTE SEGUE O FLUXO DE CÂMERA) ---
elif st.session_state.bens_lista and not st.session_state.get("concluido"):
    idx = st.session_state.idx_atual
    item = st.session_state.bens_lista[idx]
    
    st.markdown(f'<div class="barra">ITEM {idx + 1} de {len(st.session_state.bens_lista)}</div>', unsafe_allow_html=True)
    st.subheader(item["nome"])
    
    if idx not in st.session_state.inventario:
        st.session_state.inventario[idx] = {"placa": "", "serial": "", "f_fixa": None, "f_geral": None}
    
    inv = st.session_state.inventario[idx]

    # --- CAMPO 1: PATRIMÔNIO (COM SCANNER) ---
    with st.container(border=True):
        st.write("🔍 **Nº de Patrimônio (Plaqueta)**")
        if st.session_state.camera_ativa == f"scan_placa_{idx}":
            foto_placa = st.camera_input("Foque no código de barras", key=f"cam_p_{idx}")
            if foto_placa:
                with st.spinner("IA lendo plaqueta..."):
                    inv["placa"] = ocr_etiqueta(foto_placa, "número do patrimônio/plaqueta")
                st.session_state.camera_ativa = None
                st.rerun()
        else:
            col1, col2 = st.columns([0.7, 0.3])
            inv["placa"] = col1.text_input("Número lido:", value=inv["placa"], key=f"in_p_{idx}")
            if col2.button("📷 Scan", key=f"btn_p_{idx}"):
                st.session_state.camera_ativa = f"scan_placa_{idx}"; st.rerun()

    # --- CAMPO 2: SERIAL (COM SCANNER) ---
    with st.container(border=True):
        st.write("🔍 **Número de Série (Fabricante)**")
        if st.session_state.camera_ativa == f"scan_serial_{idx}":
            foto_serial = st.camera_input("Foque no S/N ou Serial", key=f"cam_s_{idx}")
            if foto_serial:
                with st.spinner("IA lendo serial..."):
                    inv["serial"] = ocr_etiqueta(foto_serial, "número de série (S/N)")
                st.session_state.camera_ativa = None
                st.rerun()
        else:
            col1, col2 = st.columns([0.7, 0.3])
            inv["serial"] = col1.text_input("S/N lido:", value=inv["serial"], key=f"in_s_{idx}")
            if col2.button("📷 Scan", key=f"btn_s_{idx}"):
                st.session_state.camera_ativa = f"scan_serial_{idx}"; st.rerun()

    # --- FOTOS DE COMPROVAÇÃO ---
    st.write("### 📸 Fotos de Comprovação")
    c1, c2 = st.columns(2)
    with c1:
        if inv["f_fixa"] is None:
            if st.session_state.camera_ativa == f"foto_fixa_{idx}":
                f1 = st.camera_input("Foto da Plaqueta Colada", key=f1_idx)
                if f1: inv["f_fixa"] = f1; st.session_state.camera_ativa = None; st.rerun()
            else:
                if st.button("📷 Plaqueta Colada", key=f"b1_{idx}"):
                    st.session_state.camera_ativa = f"foto_fixa_{idx}"; st.rerun()
        else:
            st.image(inv["f_fixa"], width=100)
            if st.button("🔄 Refazer", key=f"r1_{idx}"): inv["f_fixa"] = None; st.rerun()

    with c2:
        if inv["f_geral"] is None:
            if st.session_state.camera_ativa == f"foto_geral_{idx}":
                f2 = st.camera_input("Foto Geral", key=f2_idx)
                if f2: inv["f_geral"] = f2; st.session_state.camera_ativa = None; st.rerun()
            else:
                if st.button("📷 Bem Geral", key=f"b2_{idx}"):
                    st.session_state.camera_ativa = f"foto_geral_{idx}"; st.rerun()
        else:
            st.image(inv["f_geral"], width=100)
            if st.button("🔄 Refazer ", key=f"r2_{idx}"): inv["f_geral"] = None; st.rerun()

    st.divider()
    if st.button("Próximo Item ➡️"):
        st.session_state.idx_atual += 1
        if st.session_state.idx_atual >= len(st.session_state.bens_lista):
            st.session_state.concluido = True
        st.rerun()

# --- 6. PDF FINAL (CONTINUA IGUAL) ---
elif st.session_state.get("concluido"):
    servidor = st.text_input("Nome do Servidor:")
    if st.button("🚀 GERAR TERMO DE TOMBAMENTO"):
        pdf = FPDF(); pdf.set_margins(15, 15, 15)
        for i, it in enumerate(st.session_state.bens_lista):
            pdf.add_page()
            res = st.session_state.inventario[i]
            pdf.set_font("Arial", 'B', 16); pdf.cell(180, 10, tr("TERMO DE TOMBAMENTO"), ln=True, align='C')
            pdf.set_fill_color(240); pdf.set_font("Arial", 'B', 11)
            pdf.cell(180, 10, tr(f" ITEM: {it['nome']}"), border=1, ln=True, fill=True)
            pdf.cell(90, 10, tr(f" PATRIMÔNIO: {res['placa']}"), border=1)
            pdf.cell(90, 10, tr(f" SÉRIE: {res['serial']}"), border=1, ln=True)
            if res["f_fixa"]:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t1:
                    t1.write(res["f_fixa"].getvalue())
                    pdf.image(t1.name, x=15, y=50, w=85)
            if res["f_geral"]:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t2:
                    t2.write(res["f_geral"].getvalue())
                    pdf.image(t2.name, x=105, y=50, w=85)
        
        pdf_out = pdf.output(dest='S')
        if isinstance(pdf_out, str): pdf_out = pdf_out.encode('latin-1')
        st.download_button("📥 Baixar PDF", data=pdf_out, file_name="Tombamento.pdf")

if st.sidebar.button("Reiniciar"):
    st.session_state.clear(); st.rerun()
