import streamlit as st
from groq import Groq
import pdfplumber
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import io
from PIL import Image

# --- 1. CONFIGURAÇÃO GROQ (Apenas para carregar a lista do PDF) ---
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
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto += pagina.extract_text() + "\n"
    return texto

# --- 3. INTERFACE E ESTADO ---
st.set_page_config(page_title="Tombamento Ágil", layout="centered")

if "bens_lista" not in st.session_state: st.session_state.bens_lista = []
if "inventario" not in st.session_state: st.session_state.inventario = {}
if "idx_atual" not in st.session_state: st.session_state.idx_atual = 0
if "concluido" not in st.session_state: st.session_state.concluido = False
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.markdown("""<style>
    .barra { background-color: #004d00; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
    input { font-size: 20px !important; font-weight: bold !important; color: #004d00 !important; }
</style>""", unsafe_allow_html=True)

st.title("🛡️ Tombamento Ágil (Teclado Barcode)")

# --- 4. TELA DE CARGA ---
if not st.session_state.bens_lista:
    st.subheader("Carregar Relação de Bens")
    tab1, tab2, tab3 = st.tabs(["📊 Excel/Planilha", "📄 Analisar PDF", "📝 Manual"])
    
    with tab1:
        csv_in = st.text_area("Copie as colunas do Excel e cole aqui:")
        if st.button("Carregar Planilha"):
            try:
                df = pd.read_csv(io.StringIO(csv_in), sep=None, engine='python', header=None)
                st.session_state.bens_lista = [{"nome": str(row[0])} for _, row in df.iterrows()]
                st.rerun()
            except: st.error("Erro no formato.")

    with tab2:
        pdf_file = st.file_uploader("Suba o PDF", type="pdf")
        if pdf_file and client:
            if st.button("🔍 Extrair Lista com Groq"):
                with st.spinner("Analisando PDF..."):
                    texto = extrair_texto_pdf(pdf_file)
                    completion = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": f"Liste apenas os nomes dos bens deste texto, um por linha:\n{texto}"}]
                    )
                    itens = [l.strip("- *") for l in completion.choices[0].message.content.split('\n') if len(l.strip()) > 3]
                    st.session_state.bens_lista = [{"nome": i} for i in itens]
                    st.rerun()

    with tab3:
        txt_manual = st.text_area("Um item por linha:")
        if st.button("Carregar Lista Manual"):
            st.session_state.bens_lista = [{"nome": l.strip()} for l in txt_manual.split('\n') if l.strip()]
            st.rerun()

# --- 5. TELA DE EXECUÇÃO ---
elif st.session_state.bens_lista and not st.session_state.concluido:
    idx = st.session_state.idx_atual
    item = st.session_state.bens_lista[idx]
    
    st.markdown(f'<div class="barra">ITEM {idx + 1} de {len(st.session_state.bens_lista)}</div>', unsafe_allow_html=True)
    st.subheader(f"Inventariando: {item['nome']}")
    
    if idx not in st.session_state.inventario:
        st.session_state.inventario[idx] = {"placa": "", "serial": "", "f_fixa": None, "f_geral": None}
    
    inv = st.session_state.inventario[idx]

    # --- ENTRADA DE DADOS (O Teclado Barcode vai digitar aqui) ---
    with st.container(border=True):
        st.info("👋 Toque no campo e use o botão de scan do seu teclado.")
        inv["placa"] = st.text_input("Nº PATRIMÔNIO (Plaqueta):", value=inv["placa"], key=f"in_p_{idx}")
        inv["serial"] = st.text_input("Nº SÉRIE (Fabricante):", value=inv["serial"], key=f"in_s_{idx}")

    # --- REGISTRO FOTOGRÁFICO ---
    st.write("### 📸 Fotos de Comprovação")
    c1, c2 = st.columns(2)
    
    with c1:
        if inv["f_fixa"] is None:
            if st.session_state.camera_ativa == f"f1_{idx}":
                f1 = st.camera_input("Foto da Plaqueta Colada", key=f"cam1_{idx}")
                if f1: inv["f_fixa"] = f1; st.session_state.camera_ativa = None; st.rerun()
            elif st.button("📷 Plaqueta Colada"): st.session_state.camera_ativa = f"f1_{idx}"; st.rerun()
        else:
            st.image(inv["f_fixa"], width=150)
            if st.button("🔄 Refazer", key=f"r1_{idx}"): inv["f_fixa"] = None; st.rerun()

    with c2:
        if inv["f_geral"] is None:
            if st.session_state.camera_ativa == f"f2_{idx}":
                f2 = st.camera_input("Foto Geral do Bem", key=f"cam2_{idx}")
                if f2: inv["f_geral"] = f2; st.session_state.camera_ativa = None; st.rerun()
            elif st.button("📷 Bem Geral"): st.session_state.camera_ativa = f"f2_{idx}"; st.rerun()
        else:
            st.image(inv["f_geral"], width=150)
            if st.button("🔄 Refazer ", key=f"r2_{idx}"): inv["f_geral"] = None; st.rerun()

    st.divider()
    col_nav1, col_nav2 = st.columns(2)
    if idx > 0:
        if col_nav1.button("⬅️ Voltar"): st.session_state.idx_atual -= 1; st.rerun()
    
    if idx + 1 < len(st.session_state.bens_lista):
        if col_nav2.button("Próximo Item ➡️"):
            if inv["placa"] and inv["f_geral"]:
                st.session_state.idx_atual += 1; st.session_state.camera_ativa = None; st.rerun()
            else: st.warning("Preencha a Plaqueta e a Foto Geral.")
    else:
        if col_nav2.button("🏁 Finalizar"):
            st.session_state.concluido = True; st.rerun()

# --- 6. PDF FINAL ---
elif st.session_state.concluido:
    st.balloons()
    servidor = st.text_input("Nome do Servidor Responsável:")
    if st.button("🚀 GERAR TERMO DE TOMBAMENTO"):
        pdf = FPDF(); pdf.set_margins(15, 15, 15)
        for i, it in enumerate(st.session_state.bens_lista):
            pdf.add_page()
            res = st.session_state.inventario[i]
            pdf.set_font("Arial", 'B', 16); pdf.set_text_color(0, 77, 0)
            pdf.cell(180, 10, tr("TERMO DE TOMBAMENTO"), ln=True, align='C')
            pdf.set_fill_color(240); pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0)
            pdf.cell(180, 10, tr(f" ITEM: {it['nome'].upper()}"), border=1, ln=True, fill=True)
            pdf.cell(90, 10, tr(f" PATRIMÔNIO: {res['placa']}"), border=1)
            pdf.cell(90, 10, tr(f" SÉRIE: {res['serial']}"), border=1, ln=True)
            
            curr_y = pdf.get_y() + 5
            if res["f_fixa"]:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t1:
                    t1.write(res["f_fixa"].getvalue()); pdf.image(t1.name, x=15, y=curr_y, w=85)
            if res["f_geral"]:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t2:
                    t2.write(res["f_geral"].getvalue()); pdf.image(t2.name, x=105, y=curr_y, w=85)
            pdf.set_y(curr_y + 65)
            pdf.set_font("Arial", 'I', 9); pdf.multi_cell(180, 6, tr("\nAtesto que o bem foi conferido e identificado fisicamente."), align='C')

        pdf.add_page(); pdf.set_y(100); pdf.line(60, pdf.get_y(), 150, pdf.get_y())
        pdf.cell(180, 10, tr(servidor.upper()), align='C')
        st.download_button("📥 Baixar PDF", data=pdf.output(dest='S'), file_name="Tombamento.pdf")

if st.sidebar.button("Novo"):
    st.session_state.clear(); st.rerun()
