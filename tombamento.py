import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import json
import time
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

# --- 2. FUNÇÕES DE SCANNER IA ---
def ocr_ia(foto_bytes, instrucao):
    """Usa IA para ler dados específicos de uma foto"""
    try:
        img = Image.open(foto_bytes)
        res = model.generate_content([f"Extraia apenas o valor de: {instrucao}. Responda apenas o número/texto encontrado.", img])
        return res.text.strip()
    except: return "Erro na leitura"

# --- 3. CLASSE PDF ---
def tr(texto):
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

class TermoTombamento(FPDF):
    def header(self):
        self.set_fill_color(0, 50, 100) # Azul Marinho Institucional
        self.rect(0, 0, 210, 10, 'F')
        self.set_font("Arial", 'B', 15)
        self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", 'I', 8)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, 'C')

# --- 4. INTERFACE ---
st.set_page_config(page_title="Asset Scanner", layout="centered")
st.markdown("<style>.step { color: #003264; font-weight: bold; font-size: 18px; } .barra { background-color: #003264; color: white; padding: 10px; border-radius: 5px; }</style>", unsafe_allow_html=True)

if "bens_lista" not in st.session_state: st.session_state.bens_lista = []
if "inventario" not in st.session_state: st.session_state.inventario = {}
if "etapa" not in st.session_state: st.session_state.etapa = 1
if "idx_atual" not in st.session_state: st.session_state.idx_atual = 0

st.title("🛡️ Sistema de Tombamento Digital")

# --- 5. CARGA DA LISTA DE BENS ---
if not st.session_state.bens_lista:
    st.subheader("1. Carga da Relação de Bens")
    txt_input = st.text_area("Cole a lista de itens (um por linha) ou use o modo automático:", placeholder="Ex: Monitor Dell 24\nCadeira Giratória\nNotebook HP")
    if st.button("Carregar Lista"):
        st.session_state.bens_lista = [{"item": l.strip(), "status": "Pendente"} for l in txt_input.split('\n') if l.strip()]
        st.rerun()
else:
    # --- 6. FLUXO DE EXECUÇÃO SEQUENCIAL ---
    item_atual = st.session_state.bens_lista[st.session_state.idx_atual]
    
    st.markdown(f'<div class="barra">ITEM ATUAL: {item_atual["item"].upper()}</div>', unsafe_allow_html=True)
    st.progress((st.session_state.idx_atual + 1) / len(st.session_state.bens_lista))

    # Inicializa registro se não existir
    if st.session_state.idx_atual not in st.session_state.inventario:
        st.session_state.inventario[st.session_state.idx_atual] = {
            "plaqueta": "", "serial": "", "foto_fixada": None, "foto_geral": None
        }

    # --- PASSO 1: LEITURA DA PLAQUETA ---
    if st.session_state.etapa == 1:
        st.markdown('<p class="step">Passo 1: Scanear Plaqueta de Patrimônio</p>', unsafe_allow_html=True)
        cam_plaqueta = st.camera_input("Foque no Código de Barras da Plaqueta", key="cam_plaq")
        if cam_plaqueta:
            with st.spinner("IA lendo plaqueta..."):
                valor = ocr_ia(cam_plaqueta, "Número do Patrimônio/Plaqueta")
                st.session_state.inventario[st.session_state.idx_atual]["plaqueta"] = valor
                st.success(f"Plaqueta Identificada: {valor}")
                if st.button("Confirmar e Próximo"): 
                    st.session_state.etapa = 2
                    st.rerun()

    # --- PASSO 2: LEITURA DO SERIAL ---
    elif st.session_state.etapa == 2:
        st.markdown('<p class="step">Passo 2: Scanear Número de Série (Fabricante)</p>', unsafe_allow_html=True)
        cam_serial = st.camera_input("Foque no S/N ou Serial Number da etiqueta original", key="cam_ser")
        if cam_serial:
            with st.spinner("IA lendo serial..."):
                valor = ocr_ia(cam_serial, "Número de Série (S/N)")
                st.session_state.inventario[st.session_state.idx_atual]["serial"] = valor
                st.success(f"Serial Identificado: {valor}")
                if st.button("Confirmar e Próximo"):
                    st.session_state.etapa = 3
                    st.rerun()
        if st.button("Pular Serial"): st.session_state.etapa = 3; st.rerun()

    # --- PASSO 3: FOTO DA ETIQUETA COLADA NO BEM ---
    elif st.session_state.etapa == 3:
        st.markdown('<p class="step">Passo 3: Foto da Plaqueta Colada no Bem</p>', unsafe_allow_html=True)
        st.info("Tire uma foto que mostre a etiqueta já fixada no objeto.")
        cam_fixa = st.camera_input("Foto da Plaqueta Colada", key="cam_fixa")
        if cam_fixa:
            st.session_state.inventario[st.session_state.idx_atual]["foto_fixada"] = cam_fixa
            if st.button("Salvar e Próximo"):
                st.session_state.etapa = 4
                st.rerun()

    # --- PASSO 4: FOTO GERAL DO BEM ---
    elif st.session_state.etapa == 4:
        st.markdown('<p class="step">Passo 4: Foto Geral do Bem</p>', unsafe_allow_html=True)
        st.info("Tire uma foto de longe que mostre o estado geral do item.")
        cam_geral = st.camera_input("Foto Geral do Bem", key="cam_geral")
        if cam_geral:
            st.session_state.inventario[st.session_state.idx_atual]["foto_geral"] = cam_geral
            if st.button("🏁 Finalizar Item"):
                st.session_state.bens_lista[st.session_state.idx_atual]["status"] = "Concluído"
                if st.session_state.idx_atual + 1 < len(st.session_state.bens_lista):
                    st.session_state.idx_atual += 1
                    st.session_state.etapa = 1
                else:
                    st.session_state.etapa = 5 # Fim de tudo
                st.rerun()

    # --- FINALIZAÇÃO E PDF ---
    elif st.session_state.etapa == 5:
        st.balloons()
        st.success("🎉 Todos os bens foram tombados com sucesso!")
        servidor = st.text_input("Servidor Responsável:")
        
        if st.button("🚀 GERAR TERMO DE INVENTÁRIO"):
            try:
                pdf = TermoTombamento(); pdf.alias_nb_pages(); pdf.add_page()
                pdf.set_font("Arial", 'B', 16); pdf.cell(180, 10, tr("TERMO DE TOMBAMENTO E RESPONSABILIDADE"), ln=True, align='C')
                pdf.ln(10)

                for i, bem in enumerate(st.session_state.bens_lista):
                    inv = st.session_state.inventario[i]
                    pdf.set_fill_color(230); pdf.set_font("Arial", 'B', 12)
                    pdf.cell(180, 10, tr(f"ITEM {i+1}: {bem['item']}"), border=1, ln=True, fill=True)
                    
                    pdf.set_font("Arial", '', 10)
                    pdf.cell(90, 8, tr(f"PATRIMÔNIO: {inv['plaqueta']}"), border=1)
                    pdf.cell(90, 8, tr(f"SÉRIE: {inv['serial']}"), border=1, ln=True)
                    
                    # Fotos
                    curr_y = pdf.get_y()
                    if inv["foto_fixada"]:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(inv["foto_fixada"].getvalue())
                            pdf.image(tmp.name, x=20, y=curr_y+5, w=80)
                    
                    if inv["foto_geral"]:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(inv["foto_geral"].getvalue())
                            pdf.image(tmp.name, x=110, y=curr_y+5, w=80)
                    
                    pdf.set_y(curr_y + 65) # Espaço para as fotos
                    pdf.ln(5)

                pdf.ln(20); pdf.cell(180, 8, tr(f"Responsável: {servidor}"), align='C', ln=True)
                st.download_button("📥 Baixar PDF", data=pdf.output(dest='S'), file_name="Tombamento.pdf")
            except Exception as e: st.error(f"Erro: {e}")

# Sidebar de controle
with st.sidebar:
    st.subheader("Opções")
    if st.button("Reiniciar Processo"):
        st.session_state.clear()
        st.rerun()
    st.write("---")
    st.write("**Progresso:**")
    for i, b in enumerate(st.session_state.get("bens_lista", [])):
        cor = "✅" if b["status"] == "Concluído" else "⏳"
        st.write(f"{cor} {b['item']}")
