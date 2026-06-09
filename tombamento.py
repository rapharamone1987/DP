import streamlit as st
from groq import Groq
import pdfplumber
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import json
import time
import io
from PIL import Image

# --- 1. CONFIGURAÇÃO DO CLIENTE GROQ ---
if "GROQ_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GROQ_API_KEY"]
else:
    CHAVE_API = ""

client = None
if CHAVE_API:
    client = Groq(api_key=CHAVE_API)

# --- 2. FUNÇÕES DE APOIO ---
def tr(texto):
    """Trata acentuação para PDF"""
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def extrair_texto_pdf(pdf_file):
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto += pagina.extract_text() + "\n"
    return texto

# --- 3. INTERFACE E ESTADO ---
st.set_page_config(page_title="Tombamento Groq", layout="centered")

if "bens_lista" not in st.session_state: st.session_state.bens_lista = []
if "inventario" not in st.session_state: st.session_state.inventario = {}
if "idx_atual" not in st.session_state: st.session_state.idx_atual = 0
if "concluido" not in st.session_state: st.session_state.concluido = False

st.markdown("""<style>
    .titulo { color: #004d00; font-weight: bold; font-size: 24px; text-align: center; }
    .barra { background-color: #004d00; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; }
    .stButton>button { width: 100%; border-radius: 20px; }
</style>""", unsafe_allow_html=True)

st.title("🛡️ Sistema de Tombamento Digital")

# --- 4. TELA 0: CARGA DE DADOS ---
if not st.session_state.bens_lista:
    st.subheader("Configuração da Carga")
    tipo_carga = st.tabs(["📊 Colar Excel/CSV", "📄 Analisar PDF (Groq)", "📝 Lista Manual"])

    with tipo_carga[0]:
        csv_input = st.text_area("Cole as colunas da sua planilha aqui:")
        if st.button("Carregar Planilha"):
            try:
                df = pd.read_csv(io.StringIO(csv_input), sep=None, engine='python')
                st.session_state.bens_lista = [{"nome": str(row[0])} for _, row in df.iterrows()]
                st.rerun()
            except: st.error("Erro ao ler formato. Tente copiar e colar as células novamente.")

    with tipo_carga[1]:
        pdf_file = st.file_uploader("Suba o TR/Empenho", type="pdf")
        if pdf_file and st.button("🔍 Extrair com Groq"):
            with st.spinner("Analisando PDF..."):
                texto = extrair_texto_pdf(pdf_file)
                prompt = f"Liste apenas os nomes dos bens para tombamento contidos neste texto, um por linha:\n{texto}"
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}]
                )
                itens = [l.strip("- *") for l in completion.choices[0].message.content.split('\n') if len(l.strip()) > 3]
                st.session_state.bens_lista = [{"nome": i} for i in itens]
                st.rerun()

    with tipo_carga[2]:
        txt_manual = st.text_area("Um item por linha:")
        if st.button("Carregar Lista"):
            st.session_state.bens_lista = [{"nome": l.strip()} for l in txt_manual.split('\n') if l.strip()]
            st.rerun()

# --- 5. TELA DE EXECUÇÃO ---
elif st.session_state.bens_lista and not st.session_state.concluido:
    idx = st.session_state.idx_atual
    item = st.session_state.bens_lista[idx]
    
    st.markdown(f'<div class="barra">ITEM {idx + 1} de {len(st.session_state.bens_lista)}</div>', unsafe_allow_html=True)
    st.subheader(item["nome"])
    
    if idx not in st.session_state.inventario:
        st.session_state.inventario[idx] = {"placa": "", "serial": "", "f_fixa": None, "f_geral": None}
    
    inv = st.session_state.inventario[idx]

    # Passo 1 & 2: Dados (Usa leitor do teclado ou digitação)
    with st.expander("📝 1. Identificação Técnica", expanded=True):
        st.info("Dica: Use o ícone de 'Scan/Câmera' no teclado do celular para ler o código.")
        inv["placa"] = st.text_input("Número do Patrimônio (Plaqueta):", value=inv["placa"], key=f"p_{idx}")
        inv["serial"] = st.text_input("Número de Série (Fabricante):", value=inv["serial"], key=f"s_{idx}")

    # Passo 3 & 4: Fotos
    with st.expander("📸 2. Registro Fotográfico", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            if inv["f_fixa"] is None:
                f1 = st.camera_input("Foto da Plaqueta Colada", key=f"cam1_{idx}")
                if f1: inv["f_fixa"] = f1; st.rerun()
            else:
                st.image(inv["f_fixa"], width=150, caption="Etiqueta OK")
                if st.button("🔄 Refazer", key=f"ref1_{idx}"): inv["f_fixa"] = None; st.rerun()
        
        with col2:
            if inv["f_geral"] is None:
                f2 = st.camera_input("Foto Geral do Bem", key=f"cam2_{idx}")
                if f2: inv["f_geral"] = f2; st.rerun()
            else:
                st.image(inv["f_geral"], width=150, caption="Geral OK")
                if st.button("🔄 Refazer", key=f"ref2_{idx}"): inv["f_geral"] = None; st.rerun()

    # Navegação
    st.divider()
    c_nav1, c_nav2 = st.columns(2)
    if idx > 0:
        if c_nav1.button("⬅️ Anterior"): st.session_state.idx_atual -= 1; st.rerun()
    
    if idx + 1 < len(st.session_state.bens_lista):
        if c_nav2.button("Próximo Item ➡️"):
            if inv["placa"] and inv["f_geral"]: 
                st.session_state.idx_atual += 1; st.rerun()
            else: st.warning("Preencha ao menos a Plaqueta e a Foto Geral.")
    else:
        if c_nav2.button("🏁 Finalizar Tombamento"):
            st.session_state.concluido = True; st.rerun()

# --- 6. TELA FINAL: PDF ---
elif st.session_state.concluido:
    st.balloons()
    st.success("Tombamento concluído com sucesso!")
    servidor = st.text_input("Nome do Servidor Responsável:")
    setor = st.text_input("Setor de Destino:")

    if st.button("🚀 GERAR TERMO DE TOMBAMENTO"):
        try:
            pdf = FPDF(); pdf.set_margins(15, 15, 15)
            for i, it in enumerate(st.session_state.bens_lista):
                pdf.add_page()
                res = st.session_state.inventario[i]
                
                # Título
                pdf.set_font("Arial", 'B', 16); pdf.set_text_color(0, 77, 0)
                pdf.cell(180, 10, tr("TERMO DE TOMBAMENTO"), ln=True, align='C')
                pdf.ln(5)

                # Info Box
                pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', 10); pdf.set_text_color(0)
                pdf.cell(180, 10, tr(f" ITEM: {it['nome'].upper()}"), border=1, ln=True, fill=True)
                pdf.cell(90, 10, tr(f" PATRIMÔNIO: {res['placa']}"), border=1)
                pdf.cell(90, 10, tr(f" SÉRIE: {res['serial']}"), border=1, ln=True)
                pdf.cell(180, 10, tr(f" LOCAL: {setor.upper()}"), border=1, ln=True)
                
                # Fotos Lado a Lado
                curr_y = pdf.get_y() + 10
                if res["f_fixa"]:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t1:
                        t1.write(res["f_fixa"].getvalue())
                        pdf.image(t1.name, x=15, y=curr_y, w=85)
                if res["f_geral"]:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t2:
                        t2.write(res["f_geral"].getvalue())
                        pdf.image(t2.name, x=105, y=curr_y, w=85)
                
                pdf.set_y(curr_y + 70)
                pdf.ln(10)
                pdf.set_font("Arial", 'I', 9)
                pdf.multi_cell(180, 6, tr("Atesto para fins de inventário que o bem acima foi devidamente identificado, etiquetado e conferido nesta data."), align='C')

            # Assinatura Final
            pdf.add_page()
            pdf.set_y(100)
            pdf.line(60, pdf.get_y(), 150, pdf.get_y())
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(180, 10, tr(servidor.upper()), ln=True, align='C')
            pdf.set_font("Arial", '', 10)
            pdf.cell(180, 10, tr("Servidor Responsável"), ln=True, align='C')

            out = pdf.output(dest='S')
            if isinstance(out, str): out = out.encode('latin-1')
            st.download_button("📥 Baixar Termo PDF", data=out, file_name="Tombamento.pdf", mime="application/pdf")
        except Exception as e: st.error(f"Erro ao gerar PDF: {e}")

if st.sidebar.button("Reiniciar Sistema"):
    st.session_state.clear(); st.rerun()
