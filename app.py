import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import tempfile
import os

# --- 1. CONFIGURAÇÃO DA IA COM AUTODETECÇÃO ---
if "GOOGLE_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GOOGLE_API_KEY"]
else:
    CHAVE_API = ""

st.sidebar.title("Configuração")
if not CHAVE_API:
    CHAVE_API = st.sidebar.text_input("Insira sua Gemini API Key", type="password")
    if not CHAVE_API:
        st.info("Aguardando Chave API...")
        st.stop()

@st.cache_resource
def carregar_modelo_seguro(api_key):
    try:
        genai.configure(api_key=api_key.strip())
        
        # Lista todos os modelos disponíveis para esta chave
        modelos_disponiveis = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Define a ordem de preferência
        preferencia = [
            'models/gemini-1.5-flash', 
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-pro',
            'models/gemini-pro'
        ]
        
        selecionado = None
        for p in preferencia:
            if p in modelos_disponiveis:
                selecionado = p
                break
        
        if not selecionado:
            selecionado = modelos_disponiveis[0] # Pega o primeiro que funcionar
            
        m = genai.GenerativeModel(
            model_name=selecionado,
            system_instruction="Você é um Engenheiro de Recebimento. Extraia apenas especificações técnicas de hardware para conferência física. Ignore textos administrativos."
        )
        return m, selecionado
    except Exception as e:
        return None, str(e)

# Inicializa o modelo
model, nome_modelo = carregar_modelo_seguro(CHAVE_API)

if model:
    st.sidebar.success(f"Conectado ao: {nome_modelo}")
else:
    st.sidebar.error(f"Erro ao conectar: {nome_modelo}")
    st.stop()

# --- 2. CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Checklist IA", layout="wide")
st.markdown("<style>h1, h2, h3 { color: #009A44; } .stButton>button { background-color: #009A44; color: white; }</style>", unsafe_allow_html=True)

# --- 3. ESTADO DA SESSÃO ---
if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}

# --- 4. INTERFACE ---
st.title("📋 Checklist de Recebimento Técnico")

with st.expander("📝 Dados do Processo", expanded=True):
    col1, col2 = st.columns(2)
    arp = col1.text_input("Número da ARP / Contrato")
    fornecedor = col1.text_input("Nome do Fornecedor")
    objeto = col2.text_input("Objeto do Recebimento")
    natureza = col2.radio("Natureza", ["Consumo", "Permanente"], horizontal=True)

st.subheader("1. Documentação")
pdf_file = st.file_uploader("Suba o PDF do TR", type="pdf")

if pdf_file and not st.session_state.checklist_items:
    with st.spinner("Analisando TR..."):
        try:
            pdf_data = pdf_file.read()
            prompt = f"Liste requisitos de conferência física técnica para {objeto} contidos neste documento. Use tópicos curtos."
            response = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_data}, prompt])
            
            itens = [l.strip("- *•0123456789. ") for l in response.text.split('\n') if len(l.strip()) > 10]
            # Filtra frases conversacionais da IA
            st.session_state.checklist_items = [i for i in itens if not i.lower().startswith(("aqui", "abaixo", "conforme", "lista"))]
            st.rerun()
        except Exception as e:
            st.error(f"Erro na análise: {e}")

# --- 5. CHECKLIST ---
if st.session_state.checklist_items:
    st.subheader("2. Conferência e Evidências")
    for i, item in enumerate(st.session_state.checklist_items):
        with st.container(border=True):
            c1, c2 = st.columns([0.1, 0.9])
            st.session_state.conferidos[i] = c1.checkbox("OK", key=f"c_{i}")
            c2.write(f"**Item {i+1}:** {item}")
            foto = st.camera_input(f"Foto {i+1}", key=f"f_{i}")
            if foto: st.session_state.fotos[i] = foto

    # --- 6. GERAÇÃO DE PDF ---
    if st.button("Gerar Relatório Final"):
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(190, 10, "RELATORIO DE RECEBIMENTO TECNICO", ln=True, align='C')
            
            pdf.set_font("Arial", size=10)
            pdf.ln(5)
            pdf.cell(190, 7, f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
            pdf.cell(190, 7, f"ARP: {arp} | FORNECEDOR: {fornecedor}", ln=True)
            pdf.ln(10)

            for idx, item_txt in enumerate(st.session_state.checklist_items):
                # Codificação para evitar erro de caracteres no FPDF
                txt = item_txt.encode('latin-1', 'ignore').decode('latin-1')
                status = "CONFORME" if st.session_state.conferidos.get(idx) else "PENDENTE"
                
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
            st.download_button("📥 Baixar Relatório", data=pdf_out, file_name=f"Relatorio_{arp}.pdf")
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")

if st.sidebar.button("Reiniciar"):
    st.session_state.clear()
    st.rerun()


