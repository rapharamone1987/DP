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

# --- 1. INICIALIZAÇÃO DO ESTADO (PREVINE O ERRO ATTRIBUTEERROR) ---
if "items_lista" not in st.session_state: st.session_state.items_lista = []
if "cabecalho" not in st.session_state: st.session_state.cabecalho = {"fornecedor": "", "edital": "", "objeto": ""}
if "midia" not in st.session_state: st.session_state.midia = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None
if "natureza_final" not in st.session_state: st.session_state.natureza_final = "Consumo"

# --- 2. CONFIGURAÇÃO DA IA ---
if "GROQ_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GROQ_API_KEY"]
else:
    CHAVE_API = ""

client = Groq(api_key=CHAVE_API) if CHAVE_API else None

# --- 3. FUNÇÕES DE APOIO ---
def tr(texto):
    """Trata acentuação para PDF Latin-1"""
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def limpar_json_ia(texto):
    try:
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        return json.loads(match.group(0)) if match else json.loads(texto)
    except:
        return None

def extrair_dados_ia(pdf_file, natureza):
    texto_extraido = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages[:4]:
            texto_extraido += pagina.extract_text() + "\n"
    
    prompt = f"""Você é um fiscal de recebimento. Analise o documento para recebimento {natureza}.
    Extraia dados REAIS e FÍSICOS. Ignore cláusulas de obrigações e multas.
    Responda APENAS JSON:
    {{"fornecedor": "nome", "edital": "número da ARP", "objeto": "descrição do bem", "checklist": ["item 1", "item 2"]}}
    Texto: {texto_extraido}"""
    
    if client:
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.1)
        return limpar_json_ia(res.choices[0].message.content)
    return None

def processar_imagem_pdf(st_image):
    if st_image is None: return None
    temp_path = os.path.join(tempfile.gettempdir(), f"img_{time.time()}_{os.urandom(4).hex()}.jpg")
    img = Image.open(st_image)
    if img.mode != 'RGB': img = img.convert('RGB')
    img.save(temp_path, "JPEG", quality=75)
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
            titulo = "RELATÓRIO DE RECEBIMENTO TÉCNICO" if self.status_geral else "RELATÓRIO DE DESCONFORMIDADE TÉCNICA"
            self.cell(0, 10, tr(titulo), 0, 1, 'C')

    def footer(self):
        self.set_y(-10); self.desenhar_faixa_tricolor(291)
        self.set_y(-18); self.set_font("Arial", 'I', 7); self.set_text_color(100)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, 'C')

# --- 5. INTERFACE STREAMLIT ---
st.set_page_config(page_title="Recebimento RS", layout="centered")

st.markdown("""<style>
    .barra-v { background-color: #639d31; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-bottom: 20px; }
    .stButton>button { width: 100%; border-radius: 10px; font-weight: bold; height: 3.5em; }
</style>""", unsafe_allow_html=True)

st.title("📋 Recebimento Técnico RS")

# FASE DE CARGA
if not st.session_state.items_lista:
    natureza = st.radio("Selecione a Natureza do Bem:", ["Consumo", "Permanente"], horizontal=True)
    pdf_file = st.file_uploader("Suba o documento (PDF)", type="pdf")
    if pdf_file and st.button("🔍 ANALISAR DOCUMENTO"):
        with st.spinner("IA extraindo informações..."):
            res = extrair_dados_ia(pdf_file, natureza)
            if res:
                st.session_state.cabecalho = res
                st.session_state.items_lista = [{"id": time.time() + i, "texto": txt} for i, txt in enumerate(res['checklist'])]
                st.session_state.natureza_final = natureza
                st.rerun()

# FASE OPERACIONAL
elif st.session_state.items_lista:
    with st.container(border=True):
        st.write("### 📝 Dados do Processo (Editáveis)")
        st.info("💡 Campos vazios não aparecerão no PDF final.")
        c1, c2 = st.columns(2)
        # Edição dos campos do cabeçalho
        st.session_state.cabecalho["fornecedor"] = c1.text_input("Fornecedor:", value=st.session_state.cabecalho.get("fornecedor", ""))
        st.session_state.cabecalho["edital"] = c2.text_input("ARP / Edital / Ata:", value=st.session_state.cabecalho.get("edital", ""))
        st.session_state.cabecalho["objeto"] = st.text_area("Descrição do Bem:", value=st.session_state.cabecalho.get("objeto", ""), height=70)
        
        c3, c4 = st.columns(2)
        nf = c3.text_input("Nº Nota Fiscal:")
        qtd = c4.text_input("Quantidade:")
        placa = c3.text_input("ID / Placa / Patrimônio:")
        unidade = c4.text_input("Unidade de Destino:")
        tipo_atesto = st.selectbox("Tipo de Atesto no PDF:", ["Definitivo", "Provisório"])

    st.write("### ✅ Itens de Conferência")
    todos_ok = True
    for i, item_obj in enumerate(st.session_state.items_lista):
        uid = item_obj["id"]
        with st.container(border=True):
            col_ch, col_tx, col_ex = st.columns([0.15, 0.7, 0.15])
            st.session_state.conferidos[uid] = col_ch.checkbox("OK", key=f"ch_{uid}", value=st.session_state.conferidos.get(uid, False))
            if not st.session_state.conferidos[uid]: todos_ok = False
            item_obj["texto"] = col_tx.text_input(f"Item {uid}", value=item_obj["texto"], key=f"input_{uid}", label_visibility="collapsed")
            
            if col_ex.button("🗑️", key=f"del_{uid}"):
                st.session_state.items_lista.pop(i); st.rerun()

            if uid not in st.session_state.midia:
                t1, t2 = st.tabs(["📸 Câmera", "📁 Galeria"])
                with t1:
                    if st.session_state.camera_ativa == uid:
                        f = st.camera_input("Foto", key=f"cam_{uid}")
                        if f: st.session_state.midia[uid] = f; st.session_state.camera_ativa = None; st.rerun()
                    elif st.button("Ligar Câmera", key=f"btn_c_{uid}"): st.session_state.camera_ativa = uid; st.rerun()
                with t2:
                    up = st.file_uploader("Arquivo", key=f"up_{uid}")
                    if up: st.session_state.midia[uid] = up; st.rerun()
            else:
                st.image(st.session_state.midia[uid], width=150)
                if st.button("Remover Foto", key=f"rm_{uid}"): del st.session_state.midia[uid]; st.rerun()

    if st.button("➕ Adicionar Requisito Manual"):
        st.session_state.items_lista.append({"id": time.time(), "texto": "Nova especificação técnica"})
        st.rerun()

    obs_geral = st.text_area("Observações Gerais / Pendências:")
    servidor = st.text_input("Nome do Servidor (Atestante):")

    # --- 6. GERAÇÃO DO PDF ---
    if st.button("🚀 GERAR RELATÓRIO FINAL"):
        if not servidor: st.error("Informe o servidor.")
        else:
            try:
                pdf = PDFChecklist(status_geral=todos_ok); pdf.alias_nb_pages(); pdf.set_margins(15, 10, 15)
                
                # Coletar itens do cabeçalho que não estão vazios
                campos_cabecalho = []
                if st.session_state.cabecalho["fornecedor"]: campos_cabecalho.append(("FORNECEDOR", st.session_state.cabecalho["fornecedor"].upper()))
                if st.session_state.cabecalho["edital"]: campos_cabecalho.append(("EDITAL/ARP", st.session_state.cabecalho["edital"]))
                if nf: campos_cabecalho.append(("NOTA FISCAL", nf))
                if qtd: campos_cabecalho.append(("QUANTIDADE", qtd))
                if placa: campos_cabecalho.append(("ID/PATRIMONIO", placa.upper()))
                if unidade: campos_cabecalho.append(("UNIDADE DESTINO", unidade.upper()))

                # Loop de Itens (2 por página)
                for i, it in enumerate(st.session_state.items_lista):
                    if i % 2 == 0:
                        pdf.add_page()
                    else:
                        pdf.ln(5); pdf.set_draw_color(200); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(5)

                    # BEM (com Borda Dinâmica)
                    pdf.set_fill_color(99, 157, 49); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 10)
                    pdf.multi_cell(0, 8, tr(f" BEM: {st.session_state.cabecalho['objeto'].upper()}"), 1, 'L', fill=True)
                    
                    # RENDERIZAÇÃO DINÂMICA DO CABEÇALHO (Evita estouro)
                    pdf.set_text_color(0); pdf.set_font("Arial", '', 9); pdf.set_fill_color(245)
                    for label, valor in campos_cabecalho:
                        pdf.set_font("Arial", 'B', 9)
                        pdf.write(7, tr(f" {label}: "))
                        pdf.set_font("Arial", '', 9)
                        pdf.multi_cell(0, 7, tr(valor), 'B', 'L', False)
                    
                    pdf.ln(2)
                    # Status e Texto do Item
                    status_v = st.session_state.conferidos.get(it['id'], False)
                    desenhar_check(pdf, 17, pdf.get_y()+1, st.session_state.conferidos_status.get(it['id']))
                    pdf.set_x(25); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(165, 6, tr(it['texto']))
                    
                    # Foto
                    if it['id'] in st.session_state.midia:
                        p = processar_imagem_pdf(st.session_state.midia[it['id']])
                        if p:
                            with Image.open(p) as img:
                                p_h = 70 * (img.height/img.width)
                            if pdf.get_y() + p_h > 270: pdf.add_page()
                            pdf.image(p, x=70, y=pdf.get_y()+2, w=70)
                            pdf.set_y(pdf.get_y() + p_h + 4); os.unlink(p)
                    
                    pdf.ln(2); pdf.set_font("Arial", 'I', 8)
                    pdf.multi_cell(0, 5, tr(f"ATESTO O RECEBIMENTO {tipo_atesto.upper()} por conformidade física."), 0, 'C')

                # Rodapé do Relatório
                if pdf.get_y() > 220: pdf.add_page()
                if obs_geral:
                    pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 8, tr("OBSERVAÇÕES:"), 'T', 1)
                    pdf.set_font("Arial", '', 9); pdf.multi_cell(0, 5, tr(obs_geral), 1)
                
                pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, tr(servidor.upper()), 0, 1, 'C')
                pdf.set_font("Arial", '', 9); pdf.cell(0, 5, tr("Responsável pelo Recebimento"), 0, 1, 'C')

                st.download_button("📥 Baixar Relatório", data=pdf.output(dest='S').encode('latin-1'), file_name="Relatorio.pdf")
            except Exception as e: st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Nova Inspeção"): st.session_state.clear(); st.rerun()
