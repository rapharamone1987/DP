import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import tempfile
import os

# --- 1. CONFIGURAÇÃO DA IA SEGURA ---
# O código primeiro tenta buscar a chave nos 'Secrets' (Configurações do Streamlit Cloud)
# Se não encontrar (rodando local), ele usa uma string vazia para não travar
if "GOOGLE_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GOOGLE_API_KEY"]
else:
    CHAVE_API = "" # Deixe vazio aqui para segurança e use o campo da sidebar se necessário

# Interface na Sidebar para caso a chave não esteja nos Secrets
st.sidebar.title("Configuração")
if not CHAVE_API:
    CHAVE_API = st.sidebar.text_input("Insira sua Gemini API Key", type="password")
    if not CHAVE_API:
        st.info("Por favor, insira a chave API na lateral ou configure nos Secrets.")
        st.stop()

try:
    genai.configure(api_key=CHAVE_API.strip())
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash',
        system_instruction="Você é um Engenheiro Especialista em Recebimento Técnico. Sua tarefa é analisar o TR e listar apenas itens técnicos para conferência física (hardware, especificações). Ignore cláusulas administrativas, prazos ou valores."
    )
    st.sidebar.success("IA Conectada!")
except Exception as e:
    st.sidebar.error(f"Erro na IA: {e}")
    st.stop()

# --- 2. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Checklist IA - Recebimento", layout="wide")

st.markdown("""
    <style>
    .stButton>button { background-color: #009A44; color: white; border-radius: 5px; }
    h1, h2, h3 { color: #009A44; }
    .stCamera { border: 2px solid #009A44; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. ESTADO DA SESSÃO ---
if "checklist_items" not in st.session_state:
    st.session_state.checklist_items = []
if "fotos" not in st.session_state:
    st.session_state.fotos = {}
if "conferidos" not in st.session_state:
    st.session_state.conferidos = {}

# --- 4. INTERFACE ---
st.title("📋 Checklist de Recebimento Técnico")

with st.expander("📝 Dados do Processo", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        arp = st.text_input("Número da ARP / Contrato", placeholder="Ex: 123/2024")
        fornecedor = st.text_input("Nome do Fornecedor")
    with col2:
        objeto = st.text_input("Objeto do Recebimento")
        natureza = st.radio("Natureza", ["Consumo", "Permanente"], horizontal=True)

# --- 5. PROCESSAMENTO DO PDF ---
st.subheader("1. Documentação")
pdf_file = st.file_uploader("Suba o PDF do TR", type="pdf")

if pdf_file and not st.session_state.checklist_items:
    with st.spinner("IA extraindo requisitos técnicos..."):
        try:
            pdf_data = pdf_file.read()
            prompt = f"Liste requisitos de conferência física para {objeto} deste documento. Apenas itens técnicos curtos."
            response = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_data}, prompt])
            
            # Filtro de linhas
            itens = []
            for l in response.text.split('\n'):
                limpa = l.strip("- *•0123456789. ")
                if len(limpa) > 8 and not limpa.lower().startswith(("aqui", "abaixo", "checklist")):
                    itens.append(limpa)
            
            st.session_state.checklist_items = itens
            st.rerun()
        except Exception as e:
            st.error(f"Erro no PDF: {e}")

# --- 6. CHECKLIST ---
if st.session_state.checklist_items:
    st.subheader("2. Conferência e Fotos")
    
    for i, item in enumerate(st.session_state.checklist_items):
        with st.container(border=True):
            c1, c2 = st.columns([0.1, 0.9])
            st.session_state.conferidos[i] = c1.checkbox("OK", key=f"c_{i}")
            c2.write(f"**Item {i+1}:** {item}")
            
            foto = st.camera_input(f"Evidência {i+1}", key=f"f_{i}")
            if foto:
                st.session_state.fotos[i] = foto

    # --- 7. PDF ---
    if st.button("Gerar Relatório Final"):
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(190, 10, "RELATORIO DE RECEBIMENTO", ln=True, align='C')
            
            pdf.set_font("Arial", size=10)
            pdf.ln(5)
            pdf.cell(190, 7, f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
            pdf.cell(190, 7, f"ARP: {arp} | FORNECEDOR: {fornecedor}", ln=True)
            pdf.ln(10)

            for idx, item_txt in enumerate(st.session_state.checklist_items):
                txt = item_txt.encode('latin-1', 'ignore').decode('latin-1')
                status = "OK" if st.session_state.conferidos.get(idx) else "PENDENTE"
                
                pdf.set_font("Arial", 'B', 10)
                pdf.multi_cell(190, 7, f"{idx+1}. {txt}")
                pdf.set_font("Arial", size=10)
                pdf.cell(190, 7, f"STATUS: {status}", ln=True)
                
                if idx in st.session_state.fotos:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(st.session_state.fotos[idx].getvalue())
                        tmp_path = tmp.name
                    if pdf.get_y() > 200: pdf.add_page()
                    pdf.image(tmp_path, x=10, w=50)
                    pdf.ln(5)
                    os.unlink(tmp_path)
                pdf.ln(5)

            pdf_out = pdf.output(dest='S').encode('latin-1', errors='replace')
            st.download_button("📥 Baixar PDF", data=pdf_out, file_name="Relatorio.pdf")
        except Exception as e:
            st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Reiniciar"):
    st.session_state.clear()
    st.rerun()

