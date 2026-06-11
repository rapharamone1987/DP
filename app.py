import streamlit as st
from groq import Groq
import pdfplumber
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
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def extrair_texto_pdf(pdf_file):
    texto = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            # Pega as 3 primeiras páginas (geralmente onde estão os dados da ARP)
            for pagina in pdf.pages[:3]:
                texto += pagina.extract_text() + "\n"
    except:
        pass
    return texto

def processar_imagem_pdf(st_image):
    if st_image is None: return None
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"img_{time.time()}_{os.urandom(4).hex()}.jpg")
    img = Image.open(st_image)
    if img.mode != 'RGB': img = img.convert('RGB')
    img.save(temp_path, "JPEG", quality=70)
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

# --- 3. CLASSE PDF COM IDENTIDADE VISUAL ---
class PDFChecklist(FPDF):
    def desenhar_faixa_tricolor(self, y_pos):
        h_faixa = 6
        self.set_fill_color(99, 157, 49); self.rect(0, y_pos, 70, h_faixa, 'F')
        self.set_fill_color(227, 6, 19); self.rect(70, y_pos, 70, h_faixa, 'F')
        self.set_fill_color(255, 194, 14); self.rect(140, y_pos, 70, h_faixa, 'F')

    def header(self):
        self.desenhar_faixa_tricolor(0)
        if self.page_no() == 1:
            self.set_y(10)
            self.set_font("Arial", 'B', 14); self.set_text_color(0)
            self.cell(0, 10, tr("RELATÓRIO DE RECEBIMENTO TÉCNICO"), 0, 1, 'C')
            self.ln(2)

    def footer(self):
        self.set_y(-10); self.desenhar_faixa_tricolor(291)
        self.set_y(-18); self.set_font("Arial", 'I', 7); self.set_text_color(100)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, 'C')

# --- 4. INTERFACE STREAMLIT ---
st.set_page_config(page_title="Recebimento RS", layout="centered")

if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "dados_auto" not in st.session_state: st.session_state.dados_auto = {}
if "registros" not in st.session_state: st.session_state.registros = {}
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.markdown("""<style>
    .barra-verde { background-color: #639d31; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-bottom: 20px; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
</style>""", unsafe_allow_html=True)

st.title("📋 Recebimento Técnico RS")

# --- 5. CARGA DE DADOS ---
if not st.session_state.checklist_items:
    natureza = st.radio("Tipo de Recebimento:", ["Consumo (Definitivo)", "Permanente (Provisório)"], horizontal=True)
    pdf_file = st.file_uploader("Upload do documento", type="pdf")
    
    if pdf_file and client:
        if st.button("🔍 ANALISAR DOCUMENTO"):
            with st.spinner("IA localizando ARP e itens técnicos..."):
                try:
                    texto_pdf = extrair_texto_pdf(pdf_file)
                    
                    # PROMPT MELHORADO PARA BUSCAR ARP/ATA
                    prompt = f"""Analise este texto de um documento oficial e extraia os dados para um recebimento {natureza}.
                    IMPORTANTE: O número da ARP pode aparecer como 'Ata de Registro de Preços', 'Ata nº', 'Contrato nº' ou 'Ajuste nº'.
                    
                    Responda APENAS um JSON no formato:
                    {{
                      "fornecedor": "nome da empresa",
                      "edital": "numero da ata ou contrato encontrado",
                      "objeto": "nome curto do item",
                      "checklist": ["item real 1", "item real 2"]
                    }}
                    Texto: {texto_pdf}"""
                    
                    res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.1)
                    
                    # Limpeza para garantir JSON puro
                    raw_res = res.choices[0].message.content
                    json_str = re.search(r'\{.*\}', raw_res, re.DOTALL).group()
                    dados = json.loads(json_str)
                    
                    st.session_state.dados_auto = dados
                    st.session_state.checklist_items = dados["checklist"]
                    st.session_state.natureza_final = natureza
                    st.rerun()
                except Exception as e:
                    st.error(f"IA falhou ao processar os campos automáticos. Por favor, preencha manualmente.")
                    # Fallback para não travar o app
                    st.session_state.dados_auto = {"fornecedor": "", "edital": "", "objeto": ""}
                    st.session_state.checklist_items = ["Verificar Marca e Modelo", "Conferir integridade física", "Verificar quantidade"]
                    st.session_state.natureza_final = natureza
                    st.rerun()

# --- 6. EXECUÇÃO DO CHECKLIST ---
elif st.session_state.checklist_items:
    obj_nome = st.session_state.dados_auto.get("objeto", "BEM").upper()
    st.markdown(f'<div class="barra-verde">{obj_nome}</div>', unsafe_allow_html=True)

    with st.container(border=True):
        c1, c2 = st.columns(2)
        fornec_val = c1.text_input("Fornecedor:", value=st.session_state.dados_auto.get("fornecedor",""))
        edital_val = c2.text_input("Edital/ARP/Ata:", value=st.session_state.dados_auto.get("edital",""))
        nf_val = c1.text_input("Nº Nota Fiscal:")
        qtd_val = c2.text_input("Quantidade:")
        placa_val = c1.text_input("ID/Patrimônio:")
        unidade_dest = c2.text_input("Unidade de Destino:")

    st.write("### 📸 Itens de Conferência")
    todos_ok = True
    for i, item in enumerate(st.session_state.checklist_items):
        with st.container(border=True):
            col_ch, col_tx = st.columns([0.15, 0.85])
            st.session_state.registros[f"c_{i}"] = col_ch.checkbox("OK", key=f"check_{i}")
            if not st.session_state.registros[f"c_{i}"]: todos_ok = False
            col_tx.write(f"**{item}**")
            
            # Captura de Mídia
            if f"f_{i}" not in st.session_state.registros:
                t1, t2 = st.tabs(["📸 Câmera", "📁 Galeria"])
                with t1:
                    if st.session_state.camera_ativa == i:
                        f = st.camera_input(f"Capturar {i}", key=f"cam_{i}")
                        if f: st.session_state.registros[f"f_{i}"] = f; st.session_state.camera_ativa = None; st.rerun()
                    else:
                        if st.button("Abrir Câmera", key=f"btn_{i}"): st.session_state.camera_ativa = i; st.rerun()
                with t2:
                    up = st.file_uploader("Arquivo", key=f"up_{i}")
                    if up: st.session_state.registros[f"f_{i}"] = up; st.rerun()
            else:
                st.image(st.session_state.registros[f"f_{i}"], width=150)
                if st.button("🗑️ Remover Foto", key=f"del_{i}"): del st.session_state.registros[f"f_{i}"]; st.rerun()

    obs_geral = st.text_area("Observações Finais:")
    servidor = st.text_input("Nome do Servidor (Atestante):")

    if st.button("🚀 GERAR RELATÓRIO FINAL"):
        if not servidor: st.error("Informe o servidor.")
        else:
            try:
                pdf = PDFChecklist(); pdf.alias_nb_pages(); pdf.set_margins(15, 10, 15)
                lista_itens = st.session_state.checklist_items
                
                for i, item_txt in enumerate(lista_itens):
                    if i % 2 == 0: pdf.add_page()
                    else: 
                        pdf.ln(5); pdf.set_draw_color(200); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(5)

                    pdf.set_fill_color(99, 157, 49); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 10)
                    pdf.multi_cell(0, 8, tr(f" BEM: {st.session_state.dados_auto.get('objeto','').upper()}"), 1, 'L', fill=True)
                    
                    pdf.set_text_color(0); pdf.set_font("Arial", '', 9); pdf.set_fill_color(240)
                    pdf.cell(90, 8, tr(f" FORNECEDOR: {fornec_val.upper()}"), border=1, fill=True)
                    pdf.cell(90, 8, tr(f" EDITAL/ARP: {edital_val}"), border=1, ln=1, fill=True)
                    pdf.cell(60, 8, tr(f" NF: {nf_val}"), border=1); pdf.cell(60, 8, tr(f" QTD: {qtd_val}"), border=1)
                    pdf.cell(60, 8, tr(f" ID/PLACA: {placa_val.upper()}"), border=1, ln=1)
                    
                    pdf.ln(2); desenhar_check(pdf, 17, pdf.get_y()+1, st.session_state.registros.get(f"c_{i}"))
                    pdf.set_x(25); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(165, 7, tr(item_txt))
                    
                    if f"f_{i}" in st.session_state.registros:
                        p = processar_imagem_pdf(st.session_state.registros[f"f_{i}"])
                        if p:
                            with Image.open(p) as img:
                                w, h = img.size; aspect = h/w; print_h = 70 * aspect
                            pdf.image(p, x=70, y=pdf.get_y()+2, w=70)
                            pdf.set_y(pdf.get_y() + print_h + 5); os.unlink(p)
                    
                    pdf.ln(2); pdf.set_font("Arial", 'I', 8)
                    atesto_pdf = "RECEBIMENTO DEFINITIVO" if "Consumo" in st.session_state.natureza_final else "RECEBIMENTO PROVISÓRIO"
                    pdf.multi_cell(0, 5, tr(f"ATESTO O {atesto_pdf} do bem acima por estar em conformidade física."), 0, 'C')

                if obs_geral:
                    pdf.add_page(); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 10, tr("OBSERVAÇÕES:"), 0, 1)
                    pdf.set_font("Arial", '', 9); pdf.multi_cell(0, 6, tr(obs_geral), 1)

                if pdf.get_y() > 240: pdf.add_page()
                pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, tr(servidor.upper()), 0, 1, 'C')
                pdf.set_font("Arial", '', 9); pdf.cell(0, 5, tr("Responsável pelo Recebimento"), 0, 1, 'C')

                st.download_button("📥 Baixar Relatório", data=pdf.output(dest='S').encode('latin-1'), file_name="Relatorio.pdf")
            except Exception as e: st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Limpar Tudo"): st.session_state.clear(); st.rerun()
