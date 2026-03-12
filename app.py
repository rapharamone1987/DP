import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import json

# --- 1. CONFIGURAÇÃO DA IA ---
if "GOOGLE_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GOOGLE_API_KEY"]
else:
    CHAVE_API = "" # Insira aqui para teste local ou use a sidebar

try:
    genai.configure(api_key=CHAVE_API.strip())
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Erro na configuração da IA: {e}")

# --- 2. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Checklist IA - Recebimento", layout="wide")

# Estilo Visual
st.markdown("""
    <style>
    .stButton>button { background-color: #009A44; color: white; border-radius: 5px; }
    h1, h2, h3 { color: #009A44; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. ESTADO DA SESSÃO ---
if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
# Novos estados para os dados automáticos
if "fornecedor" not in st.session_state: st.session_state.fornecedor = ""
if "ata" not in st.session_state: st.session_state.ata = ""
if "objeto" not in st.session_state: st.session_state.objeto = ""

st.title("📋 Checklist de Recebimento Técnico")

# --- 4. UPLOAD E EXTRAÇÃO (HEADER + ITENS) ---
st.subheader("1. Documentação de Referência")
pdf_file = st.file_uploader("Suba o PDF do Termo de Referência (TR)", type="pdf")

if pdf_file and not st.session_state.checklist_items:
    with st.spinner("IA analisando o documento... Extraindo dados e requisitos."):
        try:
            pdf_data = pdf_file.read()
            
            # Prompt para extrair dados do cabeçalho e itens do checklist
            prompt = """
            Analise este documento e retorne um JSON com os seguintes campos:
            - fornecedor: Nome da empresa fornecedora ou contratada.
            - numero_ata: Número da Ata de Registro de Preços ou Contrato.
            - objeto: Descrição sucinta do objeto (ex: Veículo, Notebook).
            - checklist: Uma lista de tópicos curtos para conferência física técnica.

            REGRAS: 
            - Retorne APENAS o JSON, sem textos explicativos.
            - Se não encontrar algum dado, deixe a string vazia "".
            """
            
            conteudo = [{"mime_type": "application/pdf", "data": pdf_data}, prompt]
            response = model.generate_content(conteudo)
            
            # Limpa possíveis blocos de código markdown do JSON
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw_text)
            
            # Salva no estado da sessão
            st.session_state.fornecedor = data.get("fornecedor", "")
            st.session_state.ata = data.get("numero_ata", "")
            st.session_state.objeto = data.get("objeto", "")
            st.session_state.checklist_items = data.get("checklist", [])
            
            st.rerun()
        except Exception as e:
            st.error(f"Erro na extração de dados: {e}")

# --- 5. DADOS DO PROCESSO (AUTO-PREENCHIDOS) ---
with st.expander("📝 Dados do Processo", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        # Usamos o value vindo da session_state
        arp = st.text_input("Número da ARP / Contrato", value=st.session_state.ata)
        fornecedor = st.text_input("Nome do Fornecedor", value=st.session_state.fornecedor)
    with col2:
        objeto_final = st.text_input("Objeto do Recebimento", value=st.session_state.objeto)
        natureza = st.radio("Natureza do Bem", ["Consumo", "Permanente"], horizontal=True)
        
        # LÓGICA CONDICIONAL: Centro de Custos
        centro_custo = ""
        if natureza == "Permanente":
            centro_custo = st.text_input("Informe o Centro de Custos", placeholder="Ex: Secretaria de Saúde / Setor X")

# --- 6. EXIBIÇÃO DO CHECKLIST ---
if st.session_state.checklist_items:
    st.subheader("2. Conferência Física")
    for i, item in enumerate(st.session_state.checklist_items):
        with st.container(border=True):
            c1, c2 = st.columns([0.1, 0.9])
            st.session_state.conferidos[i] = c1.checkbox("OK", key=f"c_{i}")
            c2.write(f"**Item {i+1}:** {item}")
            foto = st.camera_input(f"Evidência {i+1}", key=f"f_{i}")
            if foto: st.session_state.fotos[i] = foto

    # --- 7. GERAÇÃO DO PDF ---
    if st.button("🏁 Gerar Relatório Final"):
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(190, 10, "RELATORIO DE RECEBIMENTO TECNICO", ln=True, align='C')
            
            pdf.set_font("Arial", size=10)
            pdf.ln(5)
            pdf.cell(190, 7, f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
            pdf.cell(190, 7, f"ARP/ATA: {arp.upper()}", ln=True)
            pdf.cell(190, 7, f"FORNECEDOR: {fornecedor.upper()}", ln=True)
            pdf.cell(190, 7, f"OBJETO: {objeto_final.upper()}", ln=True)
            if centro_custo:
                pdf.cell(190, 7, f"CENTRO DE CUSTO: {centro_custo.upper()}", ln=True)
            
            pdf.ln(10)

            for idx, item_txt in enumerate(st.session_state.checklist_items):
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
            st.download_button("📥 Baixar Relatório PDF", data=pdf_out, file_name=f"Relatorio_{arp}.pdf")
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")

if st.sidebar.button("Reiniciar"):
    st.session_state.clear()
    st.rerun()


