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

elif st.session_state.items_lista:
    obj_curto = " ".join(st.session_state.cabecalho["objeto"].split()[:6]).upper()
    st.markdown(f'<div class="barra-v">{obj_curto}</div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.write("### 📝 Dados do Processo (Editáveis)")
        c1, c2 = st.columns(2)
        st.session_state.cabecalho["fornecedor"] = c1.text_input("Fornecedor:", value=st.session_state.cabecalho["fornecedor"])
        st.session_state.cabecalho["edital"] = c2.text_input("ARP/Edital:", value=st.session_state.cabecalho["edital"])
        st.session_state.cabecalho["objeto"] = st.text_area("Objeto:", value=st.session_state.cabecalho["objeto"], height=70)
        st.session_state.cabecalho["nf"] = c1.text_input("Nº Nota Fiscal:", value=st.session_state.cabecalho.get("nf",""))
        st.session_state.cabecalho["qtd"] = c2.text_input("Quantidade:", value=st.session_state.cabecalho.get("qtd",""))
        st.session_state.cabecalho["placa"] = c1.text_input("Patrimônio:", value=st.session_state.cabecalho.get("placa",""))
        st.session_state.cabecalho["unidade"] = c2.text_input("Unidade de Destino:", value=st.session_state.cabecalho.get("unidade",""))
        tipo_atesto_ui = st.selectbox("Tipo de Atesto no PDF:", ["Definitivo", "Provisório"])

    st.write("### ✅ Itens de Conferência")
    todos_ok = True
    for i, item_obj in enumerate(st.session_state.items_lista):
        uid = item_obj["id"]
        with st.container(border=True):
            col_ch, col_tx, col_ex = st.columns([0.15, 0.7, 0.15])
            st.session_state.conferidos_status[uid] = col_ch.checkbox("OK", key=f"ch_{uid}", value=st.session_state.conferidos_status.get(uid, False))
            if not st.session_state.conferidos_status[uid]: todos_ok = False
            item_obj["texto"] = col_tx.text_input(f"txt_{uid}", value=item_obj["texto"], key=f"input_{uid}", label_visibility="collapsed")
            if col_ex.button("🗑️", key=f"del_{uid}"): st.session_state.items_lista.pop(i); st.rerun()
            
            if uid not in st.session_state.registros_media:
                t1, t2 = st.tabs(["📸 Câmera", "📁 Galeria"])
                with t1:
                    if st.session_state.camera_ativa == uid:
                        f = st.camera_input("Capturar", key=f"cam_{uid}")
                        if f: st.session_state.registros_media[uid] = f; st.session_state.camera_ativa = None; st.rerun()
                    elif st.button("Abrir Câmera", key=f"btn_c_{uid}"): st.session_state.camera_ativa = uid; st.rerun()
                with t2:
                    up = st.file_uploader("Arquivo", key=f"up_{uid}")
                    if up: st.session_state.registros_media[uid] = up; st.rerun()
            else:
                st.image(st.session_state.registros_media[uid], width=150)
                if st.button("Remover Foto", key=f"rm_{uid}"): del st.session_state.registros_media[uid]; st.rerun()

    if st.button("➕ Adicionar Requisito"):
        st.session_state.items_lista.append({"id": time.time(), "texto": "Novo requisito"})
        st.rerun()

    obs_geral = st.text_area("Observações / Justificativa:")
    servidor = st.text_input("Nome do Servidor (Atestante):")

    if st.button("🚀 GERAR RELATÓRIO"):
        if not servidor: st.error("Informe o servidor.")
        else:
            try:
                pdf = PDFRS(status_geral=todos_ok); pdf.alias_nb_pages(); pdf.set_margins(15, 10, 15)
                cab = st.session_state.cabecalho
                
                # Coleta campos do cabeçalho que não estão vazios
                campos_print = []
                if cab["fornecedor"]: campos_print.append(("FORNECEDOR", cab["fornecedor"].upper()))
                if cab["edital"]: campos_print.append(("EDITAL/ARP", cab["edital"]))
                if cab["nf"]: campos_print.append(("NOTA FISCAL", cab["nf"]))
                if cab["qtd"]: campos_print.append(("QUANTIDADE", cab["qtd"]))
                if cab["placa"]: campos_print.append(("ID/PATRIMONIO", cab["placa"].upper()))
                if cab["unidade"]: campos_print.append(("UNIDADE DESTINO", cab["unidade"].upper()))

                pdf.add_page()
                pdf.set_fill_color(99, 157, 49); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 10)
                pdf.multi_cell(0, 8, tr(f" ITEM: {cab['objeto'].upper()}"), 1, 'L', fill=True)
                pdf.set_text_color(0); pdf.set_font("Arial", '', 9); pdf.set_fill_color(245)
                for label, val in campos_print:
                    pdf.set_font("Arial", 'B', 9); pdf.write(7, tr(f" {label}: "))
                    pdf.set_font("Arial", '', 9); pdf.multi_cell(0, 7, tr(val), 'B', 'L', False)
                pdf.ln(4)

                for it in st.session_state.items_lista:
                    if pdf.get_y() > 240: pdf.add_page()
                    desenhar_check(pdf, 17, pdf.get_y()+1, st.session_state.conferidos_status.get(it['id'], False))
                    pdf.set_x(25); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(165, 6, tr(it['texto']))
                    
                    if it['id'] in st.session_state.registros_media:
                        p = processar_imagem_pdf(st.session_state.registros_media[it['id']])
                        if p:
                            with Image.open(p) as img:
                                p_h = 70 * (img.height/img.width)
                            if pdf.get_y() + p_h > 270: pdf.add_page()
                            pdf.image(p, x=70, y=pdf.get_y()+2, w=70)
                            pdf.set_y(pdf.get_y() + p_h + 4); os.unlink(p)
                    pdf.ln(2); pdf.set_draw_color(220); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(2)

                if pdf.get_y() > 220: pdf.add_page()
                at_cor = (235, 245, 235) if todos_ok else (255, 230, 230)
                pdf.set_fill_color(*at_cor); pdf.set_font("Arial", 'B', 10)
                msg = f"ATESTO O RECEBIMENTO {tipo_atesto_ui.upper()} por conformidade técnica." if todos_ok else "RELATÓRIO DE DESCONFORMIDADE TÉCNICA."
                pdf.multi_cell(0, 10, tr(msg), 1, 'C', fill=True)

                if obs_geral:
                    pdf.ln(4); pdf.set_font("Arial", 'B', 9); pdf.cell(0, 6, tr("OBSERVAÇÕES:"), 0, 1); pdf.multi_cell(0, 5, tr(obs_geral), 1)

                pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, tr(servidor.upper()), 0, 1, 'C')
                pdf.set_font("Arial", '', 9); pdf.cell(0, 5, tr("Responsável pelo Recebimento"), 0, 1, 'C')

                st.download_button("📥 Baixar PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="Relatorio.pdf", mime="application/pdf")
            except Exception as e: st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Nova Inspeção"): st.session_state.clear(); st.rerun()
