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
        return genai.GenerativeModel(model_name='gemini-1.5-flash')
    except: return None

model = inicializar_ia(CHAVE_API)

# --- 2. FUNÇÕES DE APOIO ---
def ocr_ia(foto_bytes, instrucao):
    try:
        img = Image.open(foto_bytes)
        res = model.generate_content([f"Extraia apenas o valor real de: {instrucao}. Não use 'conforme'. Responda apenas o número/texto.", img])
        return res.text.strip()
    except: return "Erro na leitura"

def tr(texto):
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

# --- 3. INTERFACE E ESTADO ---
st.set_page_config(page_title="Tombamento Patrimonial", layout="centered")

if "bens_lista" not in st.session_state: st.session_state.bens_lista = []
if "modo_operacao" not in st.session_state: st.session_state.modo_operacao = None
if "etapa" not in st.session_state: st.session_state.etapa = 0 # 0 = Config, 1-4 = Passos
if "idx_atual" not in st.session_state: st.session_state.idx_atual = 0
if "inventario" not in st.session_state: st.session_state.inventario = {}

st.markdown("""<style>
    .barra { background-color: #1E461E; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; }
    .step-box { border: 2px solid #1E461E; padding: 15px; border-radius: 10px; margin-top: 10px; }
</style>""", unsafe_allow_html=True)

st.title("📋 Registro de Tombamento")

# --- TELA 0: CONFIGURAÇÃO INICIAL (UPLOAD E MODO) ---
if not st.session_state.bens_lista:
    st.subheader("1. Configuração do Trabalho")
    
    # Escolha do Modo
    modo = st.radio("Como deseja realizar o tombamento?", 
                    ["Individualizado (Item por item com Scanner)", "Em Lote (Vários bens com fotos gerais)"],
                    help="Individual: Para eletrônicos e veículos. Lote: Para mobiliários iguais.")
    st.session_state.modo_operacao = modo

    # Carga da Lista
    st.write("---")
    st.write("**2. Carregar Lista de Bens**")
    upload_tipo = st.tabs(["📄 Upload PDF (TR/Empenho)", "📝 Digitar/Colar Lista"])
    
    with upload_tipo[0]:
        pdf_file = st.file_uploader("Suba o arquivo da lista", type="pdf")
        if pdf_file and st.button("Analisar PDF com IA"):
            with st.spinner("IA extraindo lista de bens..."):
                prompt = 'Extraia a lista de itens. Retorne JSON: {"itens": [{"nome": "item", "qtd": 1}]}'
                res = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_file.read()}, prompt])
                data = json.loads(res.text.replace("```json", "").replace("```", "").strip())
                st.session_state.bens_lista = data["itens"]
                st.rerun()

    with upload_tipo[1]:
        txt_lista = st.text_area("Digite um item por linha:")
        if st.button("Carregar Lista Manual"):
            st.session_state.bens_lista = [{"nome": l.strip(), "qtd": 1} for l in txt_lista.split('\n') if l.strip()]
            st.rerun()

# --- TELA DE EXECUÇÃO ---
elif st.session_state.bens_lista:
    
    # --- MODO INDIVIDUAL ---
    if "Individualizado" in st.session_state.modo_operacao:
        item = st.session_state.bens_lista[st.session_state.idx_atual]
        st.markdown(f'<div class="barra">ITEM {st.session_state.idx_atual + 1}: {item["nome"].upper()}</div>', unsafe_allow_html=True)
        
        # Inicializa dados do item
        if st.session_state.idx_atual not in st.session_state.inventario:
            st.session_state.inventario[st.session_state.idx_atual] = {"plaqueta": "", "serial": "", "foto_fixa": None, "foto_geral": None}
        
        inv = st.session_state.inventario[st.session_state.idx_atual]

        # ETAPAS SEQUENCIAIS
        # PASSO 1: SCANNER PLAQUETA
        if inv["plaqueta"] == "":
            st.info("🎯 **Passo 1:** Scaneie o código de barras da Plaqueta de Patrimônio.")
            cam_p = st.camera_input("Focar na Plaqueta", key=f"cp_{st.session_state.idx_atual}")
            if cam_p:
                with st.spinner("IA lendo número..."):
                    inv["plaqueta"] = ocr_ia(cam_p, "Número do Patrimônio/Plaqueta")
                st.rerun()
        
        # PASSO 2: SCANNER SERIAL
        elif inv["serial"] == "":
            st.success(f"Plaqueta lida: {inv['plaqueta']}")
            st.info("🎯 **Passo 2:** Scaneie o Número de Série (S/N) do fabricante.")
            cam_s = st.camera_input("Focar no Serial", key=f"cs_{st.session_state.idx_atual}")
            c1, c2 = st.columns(2)
            if cam_s:
                with st.spinner("IA lendo serial..."):
                    inv["serial"] = ocr_ia(cam_s, "Número de Série")
                st.rerun()
            if c1.button("Pular Serial"): inv["serial"] = "N/A"; st.rerun()
            if c2.button("Reiniciar Plaqueta"): inv["plaqueta"] = ""; st.rerun()

        # PASSO 3: FOTO PLAQUETA FIXADA
        elif inv["foto_fixa"] is None:
            st.success(f"Serial: {inv['serial']}")
            st.info("🎯 **Passo 3:** Foto da plaqueta já colada no bem.")
            f_fixa = st.camera_input("Foto da Plaqueta Colada", key=f"ff_{st.session_state.idx_atual}")
            if f_fixa:
                inv["foto_fixa"] = f_fixa
                if st.button("Confirmar Foto"): st.rerun()

        # PASSO 4: FOTO GERAL
        elif inv["foto_geral"] is None:
            st.info("🎯 **Passo 4:** Foto geral do bem (estado físico).")
            f_geral = st.camera_input("Foto Geral do Bem", key=f"fg_{st.session_state.idx_atual}")
            if f_geral:
                inv["foto_geral"] = f_geral
                if st.button("🏁 Finalizar este Item"):
                    if st.session_state.idx_atual + 1 < len(st.session_state.bens_lista):
                        st.session_state.idx_atual += 1
                    else:
                        st.session_state.etapa = 99 # FIM
                    st.rerun()

    # --- MODO LOTE ---
    else:
        st.markdown('<div class="barra">TOMBAMENTO EM LOTE</div>', unsafe_allow_html=True)
        st.write(f"Bens: {', '.join([b['nome'] for b in st.session_state.bens_lista])}")
        
        st.info("No modo lote, registre as fotos de comprovação de todo o grupo de uma vez.")
        for i in range(3):
            f_lote = st.camera_input(f"Foto de Lote {i+1}", key=f"lote_{i}")
            if f_lote: st.session_state.inventario[f"lote_{i}"] = f_lote
        
        if st.button("🏁 Finalizar Lote"):
            st.session_state.etapa = 99
            st.rerun()

# --- TELA FINAL: GERAR PDF ---
if st.session_state.get("etapa") == 99:
    st.balloons()
    st.success("Tombamento Concluído!")
    servidor = st.text_input("Servidor Responsável:")
    
    if st.button("🚀 GERAR TERMO DE TOMBAMENTO"):
        try:
            pdf = FPDF(); pdf.set_margins(15, 15, 15); pdf.add_page()
            pdf.set_font("Arial", 'B', 16); pdf.cell(180, 10, tr("TERMO DE TOMBAMENTO"), ln=True, align='C')
            
            if "Individualizado" in st.session_state.modo_operacao:
                for i, item in enumerate(st.session_state.bens_lista):
                    inv = st.session_state.inventario[i]
                    pdf.set_fill_color(240); pdf.set_font("Arial", 'B', 12)
                    pdf.cell(180, 10, tr(f"{i+1}. {item['nome']}"), border=1, ln=True, fill=True)
                    pdf.set_font("Arial", '', 10)
                    pdf.cell(90, 8, tr(f"PLAQUETA: {inv['plaqueta']}"), border=1)
                    pdf.cell(90, 8, tr(f"SERIAL: {inv['serial']}"), border=1, ln=True)
                    
                    # Fotos Lado a Lado
                    curr_y = pdf.get_y()
                    if inv["foto_fixa"]:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t1:
                            t1.write(inv["foto_fixa"].getvalue())
                            pdf.image(t1.name, x=20, y=curr_y+2, w=80)
                    if inv["foto_geral"]:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t2:
                            t2.write(inv["foto_geral"].getvalue())
                            pdf.image(t2.name, x=110, y=curr_y+2, w=80)
                    pdf.set_y(curr_y + 65)
            
            pdf.ln(20); pdf.cell(180, 8, tr(f"Servidor: {servidor}"), align='C')
            st.download_button("📥 Baixar PDF", data=pdf.output(dest='S'), file_name="Tombamento.pdf")
        except Exception as e: st.error(f"Erro no PDF: {e}")

# Sidebar
with st.sidebar:
    if st.button("Reiniciar Tudo"):
        st.session_state.clear(); st.rerun()
