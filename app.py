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

# --- 1. CONFIGURAÇÃO DA IA (GROQ) ---
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

def limpar_json_ia(texto):
    try:
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(texto)
    except:
        raise ValueError("Falha ao processar resposta da IA. Tente carregar novamente.")

def extrair_dados_ia(pdf_file, natureza):
    texto_extraido = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages[:4]:
            texto_extraido += pagina.extract_text() + "\n"
    
    prompt = f"""Analise este documento para recebimento {natureza}. 
    Extraia: Fornecedor, número da ARP/Ata/Contrato e o Objeto. 
    Crie um checklist técnico com itens reais. Responda APENAS JSON:
    {{"fornecedor": "nome", "edital": "número", "objeto": "descrição", "checklist": ["item 1", "item 2"]}}
    Texto: {texto_extraido}"""
    
    res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.1)
    return limpar_json_ia(res.choices[0].message.content)

def processar_imagem_pdf(st_image):
    if st_image is None: return None
    temp_path = os.path.join(tempfile.gettempdir(), f"img_{time.time()}_{os.urandom(4).hex()}.jpg")
    img = Image.open(st_image)
    if img.mode != 'RGB': img = img.convert('RGB')
    img.save(temp_path, "JPEG", quality=75)
    return temp_path

def desenhar_check(pdf, x, y, status):
    if status:
        pdf.set_fill_color(99, 157, 49); pdf.ellipse(x, y, 5, 5, 'F')
        pdf.set_draw_color(255, 255, 255); pdf.set_line_width(0.4)
        pdf.line(x+1.2, y+2.5, x+2.2, y+3.8); pdf.line(x+2.2, y+3.8, x+3.8, y+1.5)
    else:
        pdf.set_fill_color(227, 6, 19); pdf.ellipse(x, y, 5, 5, 'F')
        pdf.set_draw_color(255, 255, 255); pdf.set_line_width(0.4)
        pdf.line(x+1.5, y+1.5, x+3.5, y+3.5); pdf.line(x+3.5, y+1.5, x+1.5, y+3.5)
    pdf.set_line_width(0.2); pdf.set_draw_color(0, 0, 0)

# --- 3. CLASSE PDF COM IDENTIDADE RS ---
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

# --- 4. INTERFACE STREAMLIT ---
st.set_page_config(page_title="Recebimento RS", layout="centered")

if "items_lista" not in st.session_state: st.session_state.items_lista = []
if "dados_cabecalho" not in st.session_state: st.session_state.dados_cabecalho = {"fornecedor": "", "edital": "", "objeto": ""}
if "registros_media" not in st.session_state: st.session_state.registros_media = {}
if "conferidos_status" not in st.session_state: st.session_state.conferidos_status = {}
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.markdown("""<style>
    .barra-v { background-color: #639d31; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-bottom: 20px; }
    .stButton>button { width: 100%; border-radius: 10px; font-weight: bold; }
</style>""", unsafe_allow_html=True)

st.title("📋 Recebimento Técnico Inteligente")

# --- 5. CARGA E ANÁLISE ---
if not st.session_state.items_lista:
    natureza = st.radio("Natureza do Item (para busca da IA):", ["Consumo", "Permanente"], horizontal=True)
    pdf_file = st.file_uploader("Suba o documento (PDF)", type="pdf")
    if pdf_file and st.button("🔍 ANALISAR DOCUMENTO"):
        with st.spinner("IA extraindo informações..."):
            try:
                res = extrair_dados_ia(pdf_file, natureza)
                st.session_state.dados_cabecalho = {"fornecedor": res['fornecedor'], "edital": res['edital'], "objeto": res['objeto']}
                st.session_state.items_lista = [{"id": time.time() + i, "texto": txt} for i, txt in enumerate(res['checklist'])]
                st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

# --- 6. FORMULÁRIO OPERACIONAL ---
elif st.session_state.items_lista:
    obj_curto = " ".join(st.session_state.dados_cabecalho["objeto"].split()[:6]).upper()
    st.markdown(f'<div class="barra-v">{obj_curto}</div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.write("### 📝 Dados do Processo")
        c1, c2 = st.columns(2)
        st.session_state.dados_cabecalho["fornecedor"] = c1.text_input("Fornecedor:", value=st.session_state.dados_cabecalho["fornecedor"])
        st.session_state.dados_cabecalho["edital"] = c2.text_input("Edital/ARP:", value=st.session_state.dados_cabecalho["edital"])
        st.session_state.dados_cabecalho["objeto"] = st.text_area("Descrição do Objeto:", value=st.session_state.dados_cabecalho["objeto"], height=70)
        
        c3, c4 = st.columns(2)
        nf = c3.text_input("Nº Nota Fiscal:")
        qtd = c4.text_input("Quantidade:")
        placa = c3.text_input("ID / Patrimônio:")
        unidade = c4.text_input("Unidade de Destino:")

    st.write("### ✅ Itens de Conferência")
    todos_ok = True
    for i, item_obj in enumerate(st.session_state.items_lista):
        uid = item_obj["id"]
        with st.container(border=True):
            col_ch, col_tx, col_ex = st.columns([0.1, 0.75, 0.15])
            st.session_state.conferidos_status[uid] = col_ch.checkbox("", key=f"ch_{uid}", value=st.session_state.conferidos_status.get(uid, False))
            if not st.session_state.conferidos_status[uid]: todos_ok = False
            item_obj["texto"] = col_tx.text_input(f"Item {uid}", value=item_obj["texto"], key=f"input_{uid}", label_visibility="collapsed")
            if col_ex.button("🗑️", key=f"del_{uid}"):
                st.session_state.items_lista.pop(i); st.rerun()

            if uid not in st.session_state.registros_media:
                t1, t2 = st.tabs(["📸 Câmera", "📁 Galeria"])
                with t1:
                    if st.session_state.camera_ativa == uid:
                        f = st.camera_input("Capturar", key=f"cam_{uid}")
                        if f: st.session_state.registros_media[uid] = f; st.session_state.camera_ativa = None; st.rerun()
                    elif st.button("Abrir Câmera", key=f"btn_c_{uid}"): st.session_state.camera_ativa = uid; st.rerun()
                with t2:
                    up = st.file_uploader("Upload", key=f"up_{uid}")
                    if up: st.session_state.registros_media[uid] = up; st.rerun()
            else:
                st.image(st.session_state.registros_media[uid], width=150)
                if st.button("Remover Mídia", key=f"rm_{uid}"): del st.session_state.registros_media[uid]; st.rerun()

    if st.button("➕ Adicionar Requisito Manual"):
        st.session_state.items_lista.append({"id": time.time(), "texto": "Novo requisito"})
        st.rerun()

    # --- ESCOLHA DO TIPO DE ATESTO (O NOVO AJUSTE) ---
    st.write("---")
    st.write("### 🏁 Finalização")
    tipo_atesto = st.radio("Tipo de Recebimento para o Atesto Final:", ["Provisório", "Definitivo"], horizontal=True, help="Define o texto jurídico que aparecerá no PDF.")
    
    obs = st.text_area("Observações / Pendências:")
    servidor = st.text_input("Nome do Servidor (Atestante):")

    # --- GERAÇÃO DO PDF ---
    if st.button("🚀 GERAR RELATÓRIO FINAL"):
        if not servidor: st.error("Informe o servidor.")
        else:
            try:
                pdf = PDFChecklist(); pdf.alias_nb_pages(); pdf.set_margins(15, 10, 15)
                cab = st.session_state.dados_cabecalho
                for i, it in enumerate(st.session_state.items_lista):
                    if i % 2 == 0: pdf.add_page()
                    else: pdf.ln(5); pdf.set_draw_color(200); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(5)

                    pdf.set_fill_color(99, 157, 49); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 10)
                    pdf.multi_cell(0, 8, tr(f" BEM: {cab['objeto'].upper()}"), 1, 'L', fill=True)
                    
                    pdf.set_text_color(0); pdf.set_font("Arial", '', 9); pdf.set_fill_color(245)
                    pdf.cell(90, 7, tr(f" FORNECEDOR: {cab['fornecedor'].upper()}"), border=1, fill=True)
                    pdf.cell(90, 7, tr(f" EDITAL/ARP: {cab['edital']}"), border=1, ln=1, fill=True)
                    pdf.cell(45, 7, tr(f" NF: {nf}"), border=1); pdf.cell(45, 7, tr(f" QTD: {qtd}"), border=1)
                    pdf.cell(45, 7, tr(f" ID: {placa}"), border=1); pdf.cell(45, 7, tr(f" DEST: {unidade.upper()}"), border=1, ln=1)
                    
                    pdf.ln(2); status_v = st.session_state.conferidos_status.get(it['id'])
                    desenhar_check(pdf, 17, pdf.get_y()+1, status_v)
                    pdf.set_x(25); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(165, 6, tr(it['texto']))
                    
                    if it['id'] in st.session_state.registros_media:
                        img_path = processar_imagem_pdf(st.session_state.registros_media[it['id']])
                        with Image.open(img_path) as im:
                            aspect = im.height/im.width; p_h = 70 * aspect
                        pdf.image(img_path, x=70, y=pdf.get_y()+2, w=70)
                        pdf.set_y(pdf.get_y() + p_h + 4); os.unlink(img_path)
                    
                    # LOGICA DO TIPO DE ATESTO NO PDF
                    atesto_label = "RECEBIMENTO " + tipo_atesto.upper()
                    pdf.set_font("Arial", 'I', 8); pdf.multi_cell(0, 5, tr(f"ATESTO O {atesto_label} do bem acima por estar em conformidade física."), 0, 'C')

                if obs:
                    if pdf.get_y() > 220: pdf.add_page()
                    pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 8, tr("OBSERVAÇÕES:"), 'T', 1); pdf.multi_cell(0, 5, tr(obs), 1)
                
                if pdf.get_y() > 240: pdf.add_page()
                pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, tr(servidor.upper()), 0, 1, 'C')
                pdf.set_font("Arial", '', 9); pdf.cell(0, 5, tr("Responsável pelo Recebimento"), 0, 1, 'C')

                st.download_button("📥 Baixar PDF", data=pdf.output(dest='S').encode('latin-1'), file_name=f"Relatorio_{tipo_atesto}.pdf")
            except Exception as e: st.error(f"Erro: {e}")

if st.sidebar.button("Nova Inspeção"): st.session_state.clear(); st.rerun()
