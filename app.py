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
from PIL import Image

# --- 1. CONFIGURAÇÃO DA IA ---
if "GROQ_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GROQ_API_KEY"]
else:
    CHAVE_API = ""

client = Groq(api_key=CHAVE_API) if CHAVE_API else None

# --- 2. FUNÇÕES DE APOIO ---
def tr(texto):
    """Trata acentuação para PDF Latin-1"""
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def extrair_dados_ia(pdf_file, natureza):
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages[:3]: # Foca nas 3 primeiras páginas para extração de dados
            texto += pagina.extract_text() + "\n"
    
    prompt = f"""Analise este documento para recebimento {natureza}. 
    Localize: Fornecedor, número da ARP/Ata/Contrato e o Objeto. 
    Crie um checklist técnico com itens físicos reais encontrados.
    Responda APENAS um JSON:
    {{"fornecedor": "x", "edital": "x", "objeto": "x", "checklist": ["item1", "item2"]}}"""
    
    res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
    json_str = res.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    return json.loads(json_str)

def processar_imagem_pdf(st_image):
    if st_image is None: return None
    temp_path = os.path.join(tempfile.gettempdir(), f"img_{time.time()}_{os.urandom(4).hex()}.jpg")
    img = Image.open(st_image)
    if img.mode != 'RGB': img = img.convert('RGB')
    img.save(temp_path, "JPEG", quality=75)
    return temp_path

# --- 3. CLASSE PDF COM LAYOUT OTIMIZADO ---
class PDFChecklist(FPDF):
    def desenhar_faixa_tricolor(self, y_pos):
        h = 6
        self.set_fill_color(99, 157, 49); self.rect(0, y_pos, 70, h, 'F')
        self.set_fill_color(227, 6, 19); self.rect(70, y_pos, 70, h, 'F')
        self.set_fill_color(255, 194, 14); self.rect(140, y_pos, 70, h, 'F')

    def header(self):
        self.desenhar_faixa_tricolor(0)
        self.set_y(10)
        if self.page_no() == 1:
            self.set_font("Arial", 'B', 14); self.set_text_color(0)
            self.cell(0, 10, tr("RELATÓRIO DE RECEBIMENTO TÉCNICO"), 0, 1, 'C')

    def footer(self):
        self.set_y(-10); self.desenhar_faixa_tricolor(291)
        self.set_y(-18); self.set_font("Arial", 'I', 7); self.set_text_color(100)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, 'C')

# --- 4. INTERFACE ---
st.set_page_config(page_title="Recebimento RS", layout="centered")

if "checklist" not in st.session_state: st.session_state.checklist = []
if "dados" not in st.session_state: st.session_state.dados = {}
if "registros" not in st.session_state: st.session_state.registros = {}
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.markdown("""<style>
    .barra-v { background-color: #639d31; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; }
    .stButton>button { width: 100%; border-radius: 10px; font-weight: bold; height: 3.5em; }
</style>""", unsafe_allow_html=True)

st.title("📋 Recebimento Técnico RS")

# --- 5. CARGA ---
if not st.session_state.checklist:
    natureza = st.radio("Tipo:", ["Consumo (Definitivo)", "Permanente (Provisório)"], horizontal=True)
    pdf_file = st.file_uploader("Suba o PDF do TR/ARP/Empenho", type="pdf")
    if pdf_file and st.button("🔍 ANALISAR DOCUMENTO"):
        with st.spinner("IA extraindo dados técnicos..."):
            try:
                res = extrair_dados_ia(pdf_file, natureza)
                st.session_state.dados = res
                st.session_state.checklist = res["checklist"]
                st.session_state.natureza = natureza
                st.rerun()
            except: st.error("Erro na extração. Tente novamente.")

# --- 6. OPERAÇÃO ---
elif st.session_state.checklist:
    obj_curto = " ".join(st.session_state.dados.get("objeto", "").split()[:6]).upper()
    st.markdown(f'<div class="barra-v">{obj_curto}</div>', unsafe_allow_html=True)

    with st.container(border=True):
        c1, c2 = st.columns(2)
        fornec = c1.text_input("Fornecedor:", value=st.session_state.dados.get("fornecedor",""))
        arp = c2.text_input("Edital/ARP:", value=st.session_state.dados.get("edital",""))
        nf = c1.text_input("Nota Fiscal:")
        qtd = c2.text_input("Quantidade:")
        placa = c1.text_input("ID / Placa / Patrimônio:")
        unidade = c2.text_input("Unidade de Destino:")

    st.write("### Itens de Conferência")
    todos_ok = True
    for i, item in enumerate(st.session_state.checklist):
        with st.container(border=True):
            col_a, col_b = st.columns([0.15, 0.85])
            st.session_state.registros[f"c_{i}"] = col_a.checkbox("OK", key=f"ch_{i}")
            if not st.session_state.registros[f"c_{i}"]: todos_ok = False
            col_b.write(f"**{item}**")
            
            # Mídia
            if f"f_{i}" not in st.session_state.registros:
                t1, t2 = st.tabs(["📸 Câmera", "📁 Arquivo"])
                with t1:
                    if st.session_state.camera_ativa == i:
                        f = st.camera_input(f"Capturar {i}", key=f"cam_{i}", facing_mode="environment")
                        if f: st.session_state.registros[f"f_{i}"] = f; st.session_state.camera_ativa = None; st.rerun()
                    else:
                        if st.button("Abrir Câmera", key=f"btn_{i}"): st.session_state.camera_ativa = i; st.rerun()
                with t2:
                    up = st.file_uploader("Upload", key=f"up_{i}")
                    if up: st.session_state.registros[f"f_{i}"] = up; st.rerun()
            else:
                st.image(st.session_state.registros[f"f_{i}"], width=150)
                if st.button("🗑️ Remover Foto", key=f"del_{i}"): del st.session_state.registros[f"f_{i}"]; st.rerun()

    obs = st.text_area("Observações Gerais:")
    servidor = st.text_input("Servidor Responsável:")

    # --- 7. GERAÇÃO DO PDF OTIMIZADO ---
    if st.button("🚀 GERAR RELATÓRIO FINAL"):
        if not servidor: st.error("Informe o servidor.")
        else:
            try:
                pdf = PDFChecklist(); pdf.alias_nb_pages(); pdf.set_margins(15, 10, 15)
                
                for i, item_txt in enumerate(st.session_state.checklist):
                    # Lógica de 2 itens por página
                    if i % 2 == 0: pdf.add_page()
                    else: pdf.ln(5); pdf.set_draw_color(200); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(5)

                    # Cabeçalho Compacto (Barra Verde com Multi-cell para não estourar)
                    pdf.set_fill_color(99, 157, 49); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 10)
                    pdf.multi_cell(0, 8, tr(f" BEM: {st.session_state.dados.get('objeto','').upper()}"), 1, 'L', fill=True)
                    
                    # Tabela de dados
                    pdf.set_text_color(0); pdf.set_font("Arial", '', 9); pdf.set_fill_color(245)
                    pdf.cell(90, 7, tr(f" FORNECEDOR: {fornec[:45].upper()}"), border=1, fill=True)
                    pdf.cell(90, 7, tr(f" EDITAL/ARP: {arp}"), border=1, ln=1, fill=True)
                    pdf.cell(45, 7, tr(f" NF: {nf}"), border=1); pdf.cell(45, 7, tr(f" QTD: {qtd}"), border=1)
                    pdf.cell(45, 7, tr(f" ID: {placa.upper()}"), border=1); pdf.cell(45, 7, tr(f" DEST: {unidade.upper()}"), border=1, ln=1)
                    
                    # Item e Check
                    pdf.ln(2); pdf.set_font("Arial", 'B', 10)
                    status_icon = "V" if st.session_state.registros.get(f"c_{i}") else "X"
                    pdf.set_fill_color(99, 157, 49) if status_icon == "V" else pdf.set_fill_color(227, 6, 19)
                    pdf.set_text_color(255); pdf.cell(6, 6, status_icon, 0, 0, 'C', fill=True)
                    pdf.set_text_color(0); pdf.set_x(25); pdf.multi_cell(165, 6, tr(item_txt))
                    
                    # Foto do Item
                    if f"f_{i}" in st.session_state.registros:
                        img_p = processar_imagem_pdf(st.session_state.registros[f"f_{i}"])
                        if img_p:
                            with Image.open(img_p) as img:
                                w, h = img.size; aspect = h/w; print_h = 70 * aspect
                            pdf.image(img_p, x=70, y=pdf.get_y()+2, w=70)
                            pdf.set_y(pdf.get_y() + print_h + 4); os.unlink(img_p)
                    
                    pdf.set_font("Arial", 'I', 8)
                    t_atesto = "RECEBIMENTO DEFINITIVO" if "Consumo" in st.session_state.natureza else "RECEBIMENTO PROVISÓRIO"
                    pdf.multi_cell(0, 5, tr(f"ATESTO O {t_atesto} do bem acima por estar em conformidade física."), 0, 'C')

                # Observações e Assinatura (na mesma página se couber)
                if pdf.get_y() > 220: pdf.add_page()
                if obs:
                    pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 8, tr("OBSERVAÇÕES:"), 'T', 1)
                    pdf.set_font("Arial", '', 9); pdf.multi_cell(0, 5, tr(obs), 1)
                
                pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, tr(servidor.upper()), 0, 1, 'C')
                pdf.set_font("Arial", '', 9); pdf.cell(0, 5, tr("Responsável pelo Recebimento"), 0, 1, 'C')

                st.download_button("📥 Baixar Relatório", data=pdf.output(dest='S').encode('latin-1'), file_name="Recebimento.pdf", mime="application/pdf")
            except Exception as e: st.error(f"Erro: {e}")

if st.sidebar.button("Reiniciar"): st.session_state.clear(); st.rerun()
