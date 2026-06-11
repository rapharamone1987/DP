import streamlit as st
from groq import Groq
import pdfplumber
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from zoneinfo import ZoneInfo
import tempfile
import os
import io
import json
import time
import re
from PIL import Image

# --- 1. INICIALIZAÇÃO SEGURA DO ESTADO ---
if "items_lista" not in st.session_state: st.session_state.items_lista = []
if "cabecalho" not in st.session_state: 
    st.session_state.cabecalho = {"fornecedor": "", "edital": "", "objeto": "", "nf": "", "qtd": "", "placa": "", "unidade": ""}
if "registros_media" not in st.session_state: st.session_state.registros_media = {}
if "conferidos_status" not in st.session_state: st.session_state.conferidos_status = {}
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

# --- 2. CONFIGURAÇÃO DA IA ---
key = st.secrets.get("GROQ_API_KEY", "")
client = Groq(api_key=key) if key else None

def tr(texto):
    """Trata acentuação para PDF Latin-1"""
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def extrair_dados_ia(pdf_file, natureza):
    texto_extraido = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages[:4]:
            texto_extraido += pagina.extract_text() + "\n"
    
    prompt_sistema = (
        "Você é um Especialista em Recebimento de bens e materiais no setor público. "
        f"O recebimento é {natureza}. Se definitivo Liste os detalhes que devem ser conferidos, "
        "conforme o tipo de item a receber (MARCA, MODELO, Peças, cores, medidas, se está ligando, Hardware, Pintura). "
        "Se provisório, a conferencia é simplificada (MARCA/MODELO, COR, QUANTIDADE). "
        "Ignore cláusulas jurídicas. Extraia o dado real do PDF. Responda APENAS JSON: "
        '{"fornecedor": "nome", "edital": "número", "objeto": "descrição", "checklist": ["item 1", "item 2"]}'
    )
    
    if client:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[{"role": "system", "content": prompt_sistema}, {"role": "user", "content": texto_extraido}], 
            temperature=0.1
        )
        match = re.search(r'\{.*\}', res.choices[0].message.content, re.DOTALL)
        return json.loads(match.group(0)) if match else None
    return None

def processar_imagem_pdf(st_image):
    if st_image is None: return None
    temp_path = os.path.join(tempfile.gettempdir(), f"img_{time.time()}_{os.urandom(4).hex()}.jpg")
    img = Image.open(st_image)
    if img.mode != 'RGB': img = img.convert('RGB')
    img.save(temp_path, "JPEG", quality=70)
    return temp_path

def desenhar_check(pdf, x, y, status):
    cor = (99, 157, 49) if status else (227, 6, 19)
    pdf.set_fill_color(*cor); pdf.ellipse(x, y, 5, 5, 'F')
    pdf.set_draw_color(255, 255, 255); pdf.set_line_width(0.4)
    if status:
        pdf.line(x+1.2, y+2.5, x+2.2, y+3.8); pdf.line(x+2.2, y+3.8, x+3.8, y+1.5)
    else:
        pdf.line(x+1.5, y+1.5, x+3.5, y+3.5); pdf.line(x+3.5, y+1.5, x+1.5, y+3.5)
    pdf.set_line_width(0.2); pdf.set_draw_color(0, 0, 0)

# --- 3. CLASSE PDF RS ---
class PDFRS(FPDF):
    def __init__(self, status_geral=True):
        super().__init__()
        self.status_geral = status_geral

    def faixa(self, y):
        self.set_fill_color(99, 157, 49); self.rect(0, y, 70, 6, 'F')
        self.set_fill_color(227, 6, 19); self.rect(70, y, 70, 6, 'F')
        self.set_fill_color(255, 194, 14); self.rect(140, y, 70, 6, 'F')

    def header(self):
        self.faixa(0)
        self.set_y(10)
        if self.page_no() == 1:
            self.set_font("Arial", 'B', 14); self.set_text_color(0)
            titulo = "RELATÓRIO DE RECEBIMENTO TÉCNICO" if self.status_geral else "RELATÓRIO DE DESCONFORMIDADE TÉCNICA"
            self.cell(0, 10, tr(titulo), 0, 1, 'C')

    def footer(self):
        self.set_y(-10); self.faixa(291)
        self.set_y(-18); self.set_font("Arial", 'I', 7); self.set_text_color(100)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, 'C')

# --- 4. INTERFACE STREAMLIT ---
st.set_page_config(page_title="Recebimento RS", layout="centered")

st.markdown("""<style>
    .barra-v { background-color: #639d31; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-bottom: 20px; }
    .stButton>button { width: 100%; border-radius: 10px; font-weight: bold; height: 3.5em; }
</style>""", unsafe_allow_html=True)

st.title("📋 Checklist Recebimento Técnico RS")

if not st.session_state.items_lista:
    natureza = st.radio("Natureza do Item:", ["Consumo", "Permanente"], horizontal=True)
    pdf_file = st.file_uploader("Suba o documento (PDF)", type="pdf")
    if pdf_file and st.button("🔍 ANALISAR DOCUMENTO"):
        with st.spinner("Analisando..."):
            res = extrair_dados_ia(pdf_file, natureza)
            if res:
                st.session_state.cabecalho.update(res)
                st.session_state.items_lista = [{"id": time.time() + i, "texto": txt} for i, txt in enumerate(res['checklist'])]
                st.rerun()

elif st.session_st
