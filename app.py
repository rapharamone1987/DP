import streamlit as st
from groq import Groq
import pdfplumber
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import io
import json
import time
import re
from PIL import Image

# ==========================================
# 1. INICIALIZAÇÃO OBRIGATÓRIA (TOPO ABSOLUTO)
# ==========================================
# Isso impede o erro "AttributeError" garantindo que as chaves existam sempre
if "items_lista" not in st.session_state: st.session_state.items_lista = []
if "cabecalho" not in st.session_state: 
    st.session_state.cabecalho = {"fornecedor": "", "edital": "", "objeto": "", "nf": "", "qtd": "", "placa": "", "unidade": ""}
if "registros_media" not in st.session_state: st.session_state.registros_media = {}
if "conferidos_status" not in st.session_state: st.session_state.conferidos_status = {}
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None
if "atesto_tipo" not in st.session_state: st.session_state.atesto_tipo = "Definitivo"
if "texto_pdf" not in st.session_state: st.session_state.texto_pdf = ""

# Define a pasta da biblioteca
banco_atas = "banco_atas"
if not os.path.exists(banco_atas):
    try:
        os.makedirs(banco_atas, exist_ok=True)
    except:
        banco_atas = tempfile.gettempdir()

# CONFIGURAÇÃO DA IA
key = st.secrets.get("GROQ_API_KEY", "")
client = Groq(api_key=key) if key else None

# ==========================================
# 2. FUNÇÕES DE APOIO
# ==========================================
def tr(t): return str(t).encode('latin-1', 'replace').decode('latin-1')

def limpar_json_ia(texto):
    try:
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        return json.loads(match.group(0)) if match else json.loads(texto)
    except: return None

def extrair_dados_ia(texto_pdf):
    prompt = (
        "Você é um Especialista em Recebimento de bens e materiais no setor público. "
        "Analise o documento e extraia detalhes técnicos FÍSICOS REAIS (Marca, modelo, peças, medidas). "
        "Ignore cláusulas jurídicas. Responda APENAS JSON: "
        '{"fornecedor": "nome", "edital": "número", "objeto": "descrição", "checklist": ["item 1", "item 2"]}'
    )
    if client:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[{"role": "user", "content": prompt + "\n" + texto_pdf}], 
            temperature=0.1
        )
        return limpar_json_ia(res.choices[0].message.content)
    return None

def perguntar_ia(pergunta, contexto):
    if client and contexto:
        prompt = f"Responda de forma técnica e curta baseada no documento: {pergunta}\n\nDocumento:\n{contexto}"
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0)
        return res.choices[0].message.content
    return "Nenhum documento disponível para consulta."

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

# ==========================================
# 3. CLASSE PDF RS (LAYOUT PREMIUM)
# ==========================================
class PDFRS(FPDF):
    def __init__(self, status_geral=True):
        super().__init__(); self.status_geral = status_geral
    def faixa(self, y):
        self.set_fill_color(99, 157, 49); self.rect(0, y, 70, 6, 'F')
        self.set_fill_color(227, 6, 19); self.rect(70, y, 70, 6, 'F')
        self.set_fill_color(255, 194, 14); self.rect(140, y, 70, 6, 'F')
    def header(self):
        self.faixa(0); self.set_y(10)
        self.set_font("Arial", 'B', 10); self.set_text_color(0)
        self.cell(0, 6, tr("SECRETARIA DA AGRICULTURA, PECUÁRIA, PRODUÇÃO SUSTENTÁVEL E IRRIGAÇÃO"), 0, 1, 'C')
        self.set_font("Arial", 'B', 14)
        titulo = "RELATÓRIO DE RECEBIMENTO TÉCNICO" if self.status_geral else "RELATÓRIO DE DESCONFORMIDADE TÉCNICA"
        self.cell(0, 8, tr(titulo), 0, 1, 'C')
    def footer(self):
        self.set_y(-10); self.faixa(291)
        self.set_y(-18); self.set_font("Arial", 'I', 7); self.set_text_color(100)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, 'C')

# ==========================================
# 4. INTERFACE STREAMLIT
# ==========================================
st.set_page_config(page_title="Recebimento RS", layout="centered")
st.title("📋 Checklist Recebimento Técnico RS")

menu = st.tabs(["🔍 Operação", "📚 Biblioteca"])

with menu[0]:
    if not st.session_state.items_lista:
        st.subheader("Carregar Documento")
        pdf_file = st.file_uploader("Upload do PDF", type="pdf")
        col1, col2 = st.columns(2)
        
        if col1.button("🔍 Analisar com IA") and pdf_file:
            with st.spinner("Extraindo dados..."):
                with pdfplumber.open(pdf_file) as pdf:
                    st.session_state.texto_pdf = "\n".join([(p.extract_text() or "") for p in pdf.pages[:6]])
                res = extrair_dados_ia(st.session_state.texto_pdf)
                if res:
                    st.session_state.cabecalho.update(res)
                    st.session_state.items_lista = [{"id": time.time()+i, "texto": txt} for i, txt in enumerate(res['checklist'])]
                    st.rerun()

        if col2.button("🖊️ Entrada Manual"):
            if pdf_file: # Se tiver PDF, carrega texto pro chat mas deixa itens vazios
                with pdfplumber.open(pdf_file) as pdf:
                    st.session_state.texto_pdf = "\n".join([(p.extract_text() or "") for p in pdf.pages[:6]])
            st.session_state.items_lista = [{"id": time.time(), "texto": "Novo Requisito"}]
            st.rerun()

    elif st.session_state.items_lista:
        if st.session_state.texto_pdf:
            with st.expander("🤖 Chat Suporte (Dúvidas sobre o PDF)"):
                p_user = st.text_input("Sua dúvida sobre o documento:")
                if st.button("Perguntar"): st.info(f"**IA:** {perguntar_ia(p_user, st.session_state.texto_pdf)}")

        obj_label = st.session_state.cabecalho["objeto"].upper()
        st.markdown(f'<div style="background-color:#639d31;color:white;padding:10px;border-radius:5px;font-weight:bold;text-align:center;margin-bottom:20px;">CONFERÊNCIA: {obj_label}</div>', unsafe_allow_html=True)

        with st.container(border=True):
            st.write("### 📝 Dados do Processo (Editáveis)")
            c1, c2 = st.columns(2)
            st.session_state.cabecalho["fornecedor"] = c1.text_input("Fornecedor:", value=st.session_state.cabecalho["fornecedor"])
            st.session_state.cabecalho["edital"] = c2.text_input("ARP/Edital:", value=st.session_state.cabecalho["edital"])
            st.session_state.cabecalho["objeto"] = st.text_area("Descrição do Item:", value=st.session_state.cabecalho["objeto"], height=70)
            st.session_state.cabecalho["nf"] = c1.text_input("NF:", value=st.session_state.cabecalho.get("nf",""))
            st.session_state.cabecalho["qtd"] = c2.text_input("Qtd:", value=st.session_state.cabecalho.get("qtd",""))
            st.session_state.cabecalho["placa"] = c1.text_input("ID:", value=st.session_state.cabecalho.get("placa",""))
            st.session_state.cabecalho["unidade"] = c2.text_input("Unidade Destino:", value=st.session_state.cabecalho.get("unidade",""))
            st.session_state.atesto_tipo = st.selectbox("Tipo de Atesto no PDF:", ["Definitivo", "Provisório"])

        st.write("### ✅ Checklist")
        todos_ok = True
        for i, itm in enumerate(st.session_state.items_lista):
            uid = itm["id"]
            with st.container(border=True):
                col_ch, col_tx, col_ex = st.columns([0.15, 0.7, 0.15])
                st.session_state.conferidos_status[uid] = col_ch.checkbox("OK", key=f"ch_{uid}", value=st.session_state.conferidos_status.get(uid, False))
                if not st.session_state.conferidos_status.get(uid): todos_ok = False
                itm["texto"] = col_tx.text_input(f"Item {i}", itm["texto"], key=f"in_{uid}", label_visibility="collapsed")
                if col_ex.button("🗑️", key=f"del_{uid}"): st.session_state.items_lista.pop(i); st.rerun()
                
                if uid not in st.session_state.registros_media:
                    t_cam, t_gal = st.tabs(["📸 Câmera", "📁 Galeria"])
                    with t_cam:
                        if st.session_state.camera_ativa == uid:
                            f = st.camera_input("Foto", key=f"cam_{uid}")
                            if f: st.session_state.registros_media[uid] = f; st.session_state.camera_ativa = None; st.rerun()
                        elif st.button("Abrir Câmera", key=f"btn_c_{uid}"): st.session_state.camera_ativa = uid; st.rerun()
                    with t_gal:
                        up = st.file_uploader("Upload", key=f"up_{uid}")
                        if up: st.session_state.registros_media[uid] = up; st.rerun()
                else:
                    st.image(st.session_state.registros_media[uid], width=150)
                    if st.button("Remover Foto", key=f"rm_{uid}"): del st.session_state.registros_media[uid]; st.rerun()

        if st.button("➕ Adicionar Requisito"): st.session_state.items_lista.append({"id": time.time(), "texto": "Novo requisito"}); st.rerun()
        
        obs_geral = st.text_area("Justificativa / Obs:")
        servidor = st.text_input("Responsável pelo Atesto:")

        if st.button("🚀 GERAR PDF"):
            if not servidor: st.error("Informe o servidor.")
            else:
                try:
                    pdf = PDFRS(status_geral=todos_ok); pdf.
