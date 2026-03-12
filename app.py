import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import json

# --- 1. CONFIGURAÇÃO DA IA (COM AUTODETECÇÃO) ---
if "GOOGLE_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GOOGLE_API_KEY"]
else:
    CHAVE_API = ""

@st.cache_resource
def carregar_modelo_seguro(api_key):
    try:
        genai.configure(api_key=api_key.strip())
        # Lista modelos e escolhe o melhor disponível (Flash ou Pro)
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        preferencia = ['models/gemini-1.5-flash', 'models/gemini-1.5-flash-latest', 'models/gemini-1.5-pro']
        selecionado = next((p for p in preferencia if p in modelos), modelos[0])
        
        return genai.GenerativeModel(selecionado), selecionado
    except Exception as e:
        return None, str(e)

st.sidebar.title("Configuração")
if not CHAVE_API:
    CHAVE_API = st.sidebar.text_input("Insira sua Gemini API Key", type="password")
    if not CHAVE_API:
        st.info("Aguardando Chave API...")
        st.stop()

model, nome_modelo = carregar_modelo_seguro(CHAVE_API)
if model:
    st.sidebar.success(f"Conectado: {nome_modelo}")
else:
    st.sidebar.error(f"Erro: {nome_modelo}")
    st.stop()

# --- 2. ESTADO DA SESSÃO ---
if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "dados_automaticos" not in st.session_state: 
    st.session_state.dados_automaticos = {"fornecedor": "", "ata": "", "objeto": ""}

# --- 3. INTERFACE E EXTRAÇÃO ---
st.title("📋 Checklist de Recebimento Técnico")

st.subheader("1. Documentação de Referência")
pdf_file = st.file_uploader("Suba o PDF do TR", type="pdf")

if pdf_file and not st.session_state.checklist_items:
    with st.spinner("IA extraindo dados e checklist..."):
        try:
            pdf_data = pdf_file.read()
            prompt = """
            Analise este documento e retorne APENAS um JSON (sem textos extras) com:
            {
              "fornecedor": "Nome da empresa",
              "numero_ata": "Número da Ata/Contrato",
              "objeto": "Descrição do item",
              "checklist": ["item 1", "item 2", "item 3"]
            }
            Extraia apenas itens técnicos de hardware/físico para o checklist.
            """
            response = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_data}, prompt])
            
            # Limpa o texto para garantir que seja um JSON válido
            raw_json = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw_json)
            
            st.session_state.dados_automaticos = {
                "fornecedor": data.get("fornecedor", ""),
                "ata": data.get("numero_ata", ""),
                "objeto": data.get("objeto", "")
            }
            st.session_state.checklist_items = data.get("checklist", [])
            st.rerun()
        except Exception as e:
            st.error(f"Erro na extração: {e}")

# --- 4. FORMULÁRIO DE DADOS ---
with st.expander("📝 Dados do Processo", expanded=True):
    col1, col2 = st.columns(2)
    arp = col1.text_input("Número da ARP / Contrato", value=st.session_state.dados_automaticos["ata"])
    fornecedor = col1.text_input("Nome do Fornecedor", value=st.session_state.dados_automaticos["fornecedor"])
    objeto = col2.text_input("Objeto do Recebimento", value=st.session_state.dados_automaticos["objeto"])
    natureza = col2.radio("Natureza do Bem", ["Consumo", "Permanente"], horizontal=True)
    
    centro_custo = ""
    if natureza == "Permanente":
        centro_custo = st.text_input("🏢 Centro de Custos", placeholder="Para qual setor vai o bem?")

# --- 5. CHECKLIST ---
if st.session_state.checklist_items:
    st.subheader("2. Conferência Física")
    for i, item in enumerate(st.session_state.checklist_items):
        with st.container(border=True):
            c1, c2 = st.columns([0.1, 0.9])
            st.session_state.conferidos[i] = c1.checkbox("OK", key=f"c_{i}")
            c2.write(f"**Item {i+1}:** {item}")
            foto = st.camera_input(f"Foto {i+1}", key=f"f_{i}")
            if foto: st.session_state.fotos[i] = foto

    # --- 6. PDF ---
    if st.button("🏁 Gerar Relatório Final"):
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(190, 10, "RELATORIO DE RECEBIMENTO TECNICO", ln=True, align='C')
            
            pdf.set_font("Arial", size=10)
            pdf.ln(5)
            pdf.cell(190, 7, f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
            pdf.cell(190, 7, f"ARP: {arp.upper()} | FORNECEDOR: {fornecedor.upper()}", ln=True)
            pdf.cell(190, 7, f"OBJETO: {objeto.upper()}", ln=True)
            if centro_custo:
                pdf.cell(190, 7, f"CENTRO DE CUSTO: {centro_custo.upper()}", ln=True)
            pdf.ln(10)

            for idx, item_txt in enumerate(st.session_state.checklist_items):
                txt = item_txt.encode('latin-1', 'ignore').decode('latin-1')
                status = "CONFORME" if st.session_state.conferidos.get(idx) else "PENDENTE"
                pdf.set_font("Arial", 'B', 10); pdf.multi_cell(190, 7, f"{idx+1}. {txt}")
                pdf.set_font("Arial", size=10); pdf.cell(190, 7, f"STATUS: {status}", ln=True)
                
                if idx in st.session_state.fotos:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(st.session_state.fotos[idx].getvalue())
                        tmp_path = tmp.name
                    if pdf.get_y() > 200: pdf.add_page()
                    pdf.image(tmp_path, x=10, w=50); pdf.ln(5)
                    os.unlink(tmp_path)
                pdf.ln(5)

            pdf_out = pdf.output(dest='S').encode('latin-1', errors='replace')
            st.download_button("📥 Baixar PDF", data=pdf_out, file_name=f"Relatorio_{arp}.pdf")
        except Exception as e:
            st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Reiniciar"):
    st.session_state.clear()
    st.rerun()


