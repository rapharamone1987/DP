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

# --- 1. INICIALIZAÇÃO SEGURA DO ESTADO (PREVINE ATTRIBUTEERROR) ---
if "items_lista" not in st.session_state: st.session_state.items_lista = []
if "cabecalho" not in st.session_state: st.session_state.cabecalho = {"fornecedor": "", "edital": "", "objeto": ""}
if "midia" not in st.session_state: st.session_state.midia = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None
if "natureza_ia" not in st.session_state: st.session_state.natureza_ia = "Consumo"

# --- 2. CONFIGURAÇÃO DA IA ---
if "GROQ_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GROQ_API_KEY"]
else:
    CHAVE_API = ""

client = Groq(api_key=CHAVE_API) if CHAVE_API else None

# --- 3. FUNÇÕES DE APOIO ---
def tr(texto):
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def limpar_json_ia(texto):
    try:
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        return json.loads(match.group(0)) if match else json.loads(texto)
    except: return None

def extrair_dados_ia(pdf_file, natureza):
    texto_extraido = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages[:4]:
            texto_extraido += pagina.extract_text() + "\n"
    
    prompt = (
        "Você é um Especialista em Recebimento de bens públicos. "
        f"Analise para recebimento {natureza}. Liste detalhes técnicos físicos (Marca, Modelo, Medidas, etc). "
        "IGNORE cláusulas contratuais. Responda APENAS JSON: "
        '{"fornecedor": "nome", "edital": "número", "objeto": "descrição", "checklist": ["item 1", "item 2"]}'
    )
    
    if client:
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt + "\n" + texto_extraido}], temperature=0.1)
        return limpar_json_ia(res.choices[0].message.content)
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

# --- 4. CLASSE PDF (ESTILO RS) ---
class PDFChecklist(FPDF):
    def __init__(self, status_geral=True):
        super().__init__()
        self.status_geral = status_geral

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
            titulo = "RELATÓRIO DE RECEBIMENTO TÉCNICO" if self.status_geral else "SECRETARIA DA AGRICULTURA, PECUÁRIA, PRODUÇÃO SUSTENTÁVEL E IRRIGAÇÃO - RELATÓRIO DE DESCONFORMIDADE TÉCNICA"
            self.cell(0, 10, tr(titulo), 0, 1, 'C')

    def footer(self):
        self.set_y(-10); self.desenhar_faixa_tricolor(291)
        self.set_y(-18); self.set_font("Arial", 'I', 7); self.set_text_color(100)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, 'C')

# --- 5. INTERFACE ---
st.set_page_config(page_title="Recebimento de Bens e Materiais", layout="centered")
st.title("📋 Checklist Recebimento Técnico RS")

if not st.session_state.items_lista:
    st.session_state.natureza_ia = st.radio("Natureza do Item:", ["Consumo", "Permanente"], horizontal=True)
    pdf_file = st.file_uploader("Suba o PDF", type="pdf")
    if pdf_file and st.button("🔍 ANALISAR DOCUMENTO"):
        with st.spinner("Extraindo dados..."):
            res = extrair_dados_ia(pdf_file, st.session_state.natureza_ia)
            if res:
                st.session_state.cabecalho = res
                st.session_state.items_lista = [{"id": time.time() + i, "texto": txt} for i, txt in enumerate(res['checklist'])]
                st.rerun()

elif st.session_state.items_lista:
    with st.container(border=True):
        st.write("### 📝 Dados do Processo")
        c1, c2 = st.columns(2)
        st.session_state.cabecalho["fornecedor"] = c1.text_input("Fornecedor:", value=st.session_state.cabecalho.get("fornecedor", ""))
        st.session_state.cabecalho["edital"] = c2.text_input("ARP/Edital:", value=st.session_state.cabecalho.get("edital", ""))
        st.session_state.cabecalho["objeto"] = st.text_area("Objeto:", value=st.session_state.cabecalho.get("objeto", ""), height=70)
        nf = c1.text_input("Nº Nota Fiscal:")
        qtd = c2.text_input("Quantidade:")
        placa = c1.text_input("Patrimônio:")
        unidade = c2.text_input("Unidade de Destino:")
        tipo_atesto_ui = st.selectbox("Tipo de Atesto no PDF:", ["Definitivo", "Provisório"])

    st.write("### ✅ Conferência")
    todos_ok = True
    for i, item_obj in enumerate(st.session_state.items_lista):
        uid = item_obj["id"]
        with st.container(border=True):
            col_ch, col_tx, col_ex = st.columns([0.15, 0.7, 0.15])
            
            # Correção do erro de atributo usando .get() com fallback
            st.session_state.conferidos[uid] = col_ch.checkbox("OK", key=f"ch_{uid}", value=st.session_state.conferidos.get(uid, False))
            if not st.session_state.conferidos[uid]: todos_ok = False
            
            item_obj["texto"] = col_tx.text_input(f"txt_{uid}", value=item_obj["texto"], key=f"input_{uid}", label_visibility="collapsed")
            if col_ex.button("🗑️", key=f"del_{uid}"):
                st.session_state.items_lista.pop(i)
                st.rerun()
            
            if uid not in st.session_state.midia:
                t1, t2 = st.tabs(["📸 Câmera", "📁 Arquivo"])
                with t1:
                    if st.session_state.camera_ativa == uid:
                        f = st.camera_input("Capturar", key=f"cam_{uid}")
                        if f: st.session_state.midia[uid] = f; st.session_state.camera_ativa = None; st.rerun()
                    elif st.button("Abrir Câmera", key=f"btn_c_{uid}"): st.session_state.camera_ativa = uid; st.rerun()
                with t2:
                    up = st.file_uploader("Upload", key=f"up_{uid}")
                    if up: st.session_state.midia[uid] = up; st.rerun()
            else:
                st.image(st.session_state.midia[uid], width=150)
                if st.button("Remover Foto", key=f"rm_{uid}"): del st.session_state.midia[uid]; st.rerun()

    if st.button("➕ Adicionar Requisito"):
        st.session_state.items_lista.append({"id": time.time(), "texto": "Novo requisito"})
        st.rerun()

    obs_geral = st.text_area("Observações / Justificativa:")
    servidor = st.text_input("Nome do Servidor:")

    # --- 6. GERAÇÃO DO PDF ---
    if st.button("🚀 GERAR RELATÓRIO"):
        if not servidor: st.error("Informe o servidor.")
        else:
            try:
                pdf = PDFChecklist(status_geral=todos_ok); pdf.alias_nb_pages(); pdf.set_margins(15, 10, 15)
                cab = st.session_state.cabecalho
                
                # Coleta campos do cabeçalho que não estão vazios
                campos_print = []
                if cab["fornecedor"]: campos_print.append(("FORNECEDOR", cab["fornecedor"].upper()))
                if cab["edital"]: campos_print.append(("EDITAL/ARP", cab["edital"]))
                if nf: campos_print.append(("NOTA FISCAL", nf))
                if qtd: campos_print.append(("QUANTIDADE", qtd))
                if placa: campos_print.append(("ID/PATRIMONIO", placa.upper()))
                if unidade: campos_print.append(("UNIDADE DESTINO", unidade.upper()))

                pdf.add_page()
                # Imprime cabeçalho inicial
                pdf.set_fill_color(99, 157, 49); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 10)
                pdf.multi_cell(0, 8, tr(f" ITEM: {cab['objeto'].upper()}"), 1, 'L', fill=True)
                pdf.set_text_color(0); pdf.set_font("Arial", '', 9); pdf.set_fill_color(245)
                for label, val in campos_print:
                    pdf.set_font("Arial", 'B', 9); pdf.write(7, tr(f" {label}: "))
                    pdf.set_font("Arial", '', 9); pdf.multi_cell(0, 7, tr(val), 'B', 'L', False)
                pdf.ln(4)

                for it in st.session_state.items_lista:
                    if pdf.get_y() > 240: pdf.add_page() # Se não couber o próximo item, pula página

                    desenhar_check(pdf, 17, pdf.get_y()+1, st.session_state.conferidos.get(it['id'], False))
                    pdf.set_x(25); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(165, 6, tr(it['texto']))
                    
                    if it['id'] in st.session_state.midia:
                        img_p = processar_imagem_pdf(st.session_state.midia[it['id']])
                        if img_p:
                            with Image.open(img_p) as im_f:
                                p_h = 50 * (im_f.height/im_f.width)
                            if pdf.get_y() + p_h > 270: pdf.add_page()
                            pdf.image(img_p, x=80, y=pdf.get_y()+1, w=50)
                            pdf.set_y(pdf.get_y() + p_h + 4); os.unlink(img_p)
                    pdf.ln(2); pdf.set_draw_color(220); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(2)

                if pdf.get_y() > 220: pdf.add_page()
                pdf.ln(5); at_cor = (235, 245, 235) if todos_ok else (255, 230, 230)
                pdf.set_fill_color(*at_cor); pdf.set_font("Arial", 'B', 10)
                msg = f"ATESTO O RECEBIMENTO {tipo_atesto_ui.upper()} por conformidade técnica." if todos_ok else "RELATÓRIO DE DESCONFORMIDADE: Itens não atendem aos requisitos."
                pdf.multi_cell(0, 10, tr(msg), 1, 'C', fill=True)

                if obs_geral:
                    pdf.ln(4); pdf.set_font("Arial", 'B', 9); pdf.cell(0, 6, tr("OBSERVAÇÕES:"), 0, 1); pdf.multi_cell(0, 5, tr(obs_geral), 1)

                pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, tr(servidor.upper()), 0, 1, 'C')
                pdf.set_font("Arial", '', 9); pdf.cell(0, 5, tr("Responsável pelo Recebimento"), 0, 1, 'C')

                st.download_button("📥 Baixar PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="Relatorio.pdf", mime="application/pdf")
            except Exception as e: st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Reiniciar"): st.session_state.clear(); st.rerun()
