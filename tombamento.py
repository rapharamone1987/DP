import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import json
import time
import re
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
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        selecionado = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in modelos else modelos[0]
        return genai.GenerativeModel(model_name=selecionado)
    except: return None

model = inicializar_ia(CHAVE_API)

# --- 2. FUNÇÕES DE APOIO ---
def ocr_ia(foto_bytes, instrucao):
    try:
        img = Image.open(foto_bytes)
        res = model.generate_content([f"Extraia o valor de: {instrucao}. Responda APENAS o número ou texto encontrado.", img])
        return res.text.strip()
    except: return "Erro na leitura"

def tr(texto):
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

# --- 3. INTERFACE E ESTADO ---
st.set_page_config(page_title="Tombamento Patrimonial", layout="centered")

if "bens_lista" not in st.session_state: st.session_state.bens_lista = []
if "modo_operacao" not in st.session_state: st.session_state.modo_operacao = None
if "idx_atual" not in st.session_state: st.session_state.idx_atual = 0
if "inventario" not in st.session_state: st.session_state.inventario = {}
if "tentou_ia" not in st.session_state: st.session_state.tentou_ia = False

st.markdown("""<style>
    .barra { background-color: #004d00; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; }
    .stButton>button { width: 100%; }
</style>""", unsafe_allow_html=True)

st.title("🛡️ Sistema de Tombamento")

# --- TELA 0: CARGA DA LISTA ---
if not st.session_state.bens_lista:
    st.subheader("Configuração do Tombamento")
    
    modo = st.radio("Selecione o modo:", ["Individualizado (Scanner)", "Em Lote (Fotos Gerais)"])
    st.session_state.modo_operacao = modo

    st.write("---")
    st.write("**Carregar Relação de Bens**")
    
    pdf_file = st.file_uploader("Suba o PDF (TR/Empenho)", type="pdf")
    
    col1, col2 = st.columns(2)
    
    if col1.button("🔍 Analisar PDF com IA"):
        if pdf_file:
            with st.spinner("IA extraindo lista... Isso pode levar 20 segundos."):
                try:
                    # Prompt simplificado para evitar que a IA "trave" pensando
                    prompt = "Liste os itens deste documento para tombamento. Retorne APENAS os nomes dos itens, um por linha."
                    res = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_file.read()}, prompt])
                    
                    itens = [l.strip("- *") for l in res.text.split('\n') if len(l.strip()) > 3]
                    if itens:
                        st.session_state.bens_lista = [{"nome": i, "qtd": 1} for i in itens]
                        st.rerun()
                    else:
                        st.error("IA não encontrou itens. Tente o modo manual ao lado.")
                except Exception as e:
                    st.error(f"Erro na IA: {e}. Use o modo manual.")
                    st.session_state.tentou_ia = True
        else:
            st.warning("Selecione um PDF primeiro.")

    if col2.button("📝 Entrada Manual"):
        st.session_state.tentou_ia = True

    if st.session_state.tentou_ia:
        txt_manual = st.text_area("Cole ou digite a lista de bens (um por linha):", placeholder="Ex: Cadeira\nMonitor\nNotebook")
        if st.button("Confirmar Lista Manual"):
            st.session_state.bens_lista = [{"nome": l.strip(), "qtd": 1} for l in txt_manual.split('\n') if l.strip()]
            st.rerun()

# --- TELA DE EXECUÇÃO ---
elif st.session_state.bens_lista:
    item = st.session_state.bens_lista[st.session_state.idx_atual]
    st.markdown(f'<div class="barra">ITEM {st.session_state.idx_atual + 1} de {len(st.session_state.bens_lista)}</div>', unsafe_allow_html=True)
    st.subheader(item["nome"])

    if "Individualizado" in st.session_state.modo_operacao:
        if st.session_state.idx_atual not in st.session_state.inventario:
            st.session_state.inventario[st.session_state.idx_atual] = {"plaqueta": "", "serial": "", "foto_fixa": None, "foto_geral": None}
        
        inv = st.session_state.inventario[st.session_state.idx_atual]

        # FLUXO SEQUENCIAL DE CÂMERAS
        if inv["plaqueta"] == "":
            st.info("📷 **Passo 1:** Scaneie o código de barras da Plaqueta.")
            cam = st.camera_input("Scanner de Plaqueta", key=f"p_{st.session_state.idx_atual}")
            if cam:
                with st.spinner("Lendo número..."):
                    inv["plaqueta"] = ocr_ia(cam, "Número do Patrimônio/Plaqueta")
                st.rerun()
        
        elif inv["serial"] == "":
            st.success(f"Plaqueta: {inv['plaqueta']}")
            st.info("📷 **Passo 2:** Scaneie o Número de Série do fabricante.")
            cam = st.camera_input("Scanner de Serial", key=f"s_{st.session_state.idx_atual}")
            if cam:
                with st.spinner("Lendo serial..."):
                    inv["serial"] = ocr_ia(cam, "Serial Number / SN")
                st.rerun()
            if st.button("Pular Serial (N/A)"): inv["serial"] = "N/A"; st.rerun()

        elif inv["foto_fixa"] is None:
            st.success(f"Serial: {inv['serial']}")
            st.info("📷 **Passo 3:** Foto da plaqueta colada no bem.")
            cam = st.camera_input("Foto da Fixação", key=f"f_{st.session_state.idx_atual}")
            if cam:
                inv["foto_fixa"] = cam
                if st.button("Confirmar Foto"): st.rerun()

        elif inv["foto_geral"] is None:
            st.info("📷 **Passo 4:** Foto geral do bem.")
            cam = st.camera_input("Foto Geral", key=f"g_{st.session_state.idx_atual}")
            if cam:
                inv["foto_geral"] = cam
                if st.button("🏁 Finalizar Item"):
                    if st.session_state.idx_atual + 1 < len(st.session_state.bens_lista):
                        st.session_state.idx_atual += 1
                    else:
                        st.session_state.concluido = True
                    st.rerun()

    # --- FINALIZAÇÃO ---
    if st.session_state.get("concluido"):
        st.balloons()
        servidor = st.text_input("Nome do Servidor:")
        if st.button("🚀 GERAR PDF"):
            try:
                pdf = FPDF(); pdf.set_margins(15, 15, 15); pdf.add_page()
                pdf.set_font("Arial", 'B', 16); pdf.cell(180, 10, tr("TERMO DE TOMBAMENTO"), ln=True, align='C')
                
                for i, it in enumerate(st.session_state.bens_lista):
                    res = st.session_state.inventario[i]
                    pdf.set_fill_color(240); pdf.set_font("Arial", 'B', 12)
                    pdf.cell(180, 10, tr(f"{i+1}. {it['nome']}"), border=1, ln=True, fill=True)
                    pdf.set_font("Arial", '', 10)
                    pdf.cell(90, 8, tr(f"PLAQUETA: {res['plaqueta']}"), border=1)
                    pdf.cell(90, 8, tr(f"SERIAL: {res['serial']}"), border=1, ln=True)
                    
                    # Fotos
                    curr_y = pdf.get_y()
                    if res["foto_fixa"]:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t1:
                            t1.write(res["foto_fixa"].getvalue())
                            pdf.image(t1.name, x=20, y=curr_y+2, w=75)
                    if res["foto_geral"]:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t2:
                            t2.write(res["foto_geral"].getvalue())
                            pdf.image(t2.name, x=105, y=curr_y+2, w=75)
                    pdf.set_y(curr_y + 60)
                
                pdf.ln(10); pdf.cell(180, 10, tr(f"Responsável: {servidor}"), align='C')
                st.download_button("📥 Baixar Termo", data=pdf.output(dest='S'), file_name="Tombamento.pdf")
            except Exception as e: st.error(f"Erro no PDF: {e}")

# Sidebar
with st.sidebar:
    if st.button("Reiniciar Sistema"):
        st.session_state.clear(); st.rerun()
