import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import tempfile
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Checklist IA - Recebimento", layout="wide")

# --- 1. CONFIGURAÇÃO DA IA ---
CHAVE_PADRAO = "AIzaSyBEaSvGFjrICM70M8IRD-X9i7n6C15IWdc" 

st.sidebar.title("Configuração")
chave_usuario = st.sidebar.text_input("Chave API Google Gemini", value=CHAVE_PADRAO, type="password")

@st.cache_resource
def configurar_ia(chave):
    try:
        genai.configure(api_key=chave.strip())
        # Tenta listar para validar a conexão
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        modelo_nome = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in modelos else modelos[0]
        return genai.GenerativeModel(modelo_nome), f"Modelo: {modelo_nome}"
    except Exception as e:
        return None, str(e)

model, status_msg = configurar_ia(chave_usuario)

# --- ESTADO DA SESSÃO ---
if "checklist_items" not in st.session_state:
    st.session_state.checklist_items = []
if "fotos" not in st.session_state:
    st.session_state.fotos = {}

# --- INTERFACE ---
st.title("📋 Checklist de Recebimento Técnico")

if model is None:
    st.error(f"Erro na IA: {status_msg}")
    st.stop()

with st.expander("Dados do Processo", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        arp = st.text_input("Número da ARP / Contrato", "123/2024")
        fornecedor = st.text_input("Nome do Fornecedor", "Empresa Exemplo")
    with col2:
        objeto = st.text_input("Objeto do Recebimento", "Ex: Notebook")
        natureza = st.radio("Natureza", ["Consumo", "Permanente"], horizontal=True)

# --- PROCESSAMENTO DO PDF ---
st.subheader("1. Documentação de Referência")
pdf_file = st.file_uploader("Suba o PDF do TR", type="pdf")

if pdf_file and not st.session_state.checklist_items:
    with st.spinner("IA extraindo requisitos..."):
        try:
            pdf_data = pdf_file.read()
            prompt = f"Extraia uma lista de itens técnicos para conferência física de {objeto} baseada neste documento. Seja curto e objetivo."
            response = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_data}, prompt])
            
            itens = [l.strip("- *0123456789. ") for l in response.text.split('\n') if len(l.strip()) > 5]
            st.session_state.checklist_items = itens
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao analisar PDF: {e}")

# --- CHECKLIST (ESTABILIZADO) ---
if st.session_state.checklist_items:
    st.subheader("2. Conferência Física e Fotos")
    
    conferencias = []
    
    for i, item in enumerate(st.session_state.checklist_items):
        # Container único por item para evitar o erro de removeChild
        with st.container(border=True):
            c1, c2 = st.columns([0.1, 0.9])
            
            # Status de OK
            status_ok = c1.checkbox("OK", key=f"chk_{i}")
            c2.markdown(f"**Item {i+1}:** {item}")
            
            # Câmera (fora de colunas apertadas para evitar erro de JS)
            # Guardamos a foto no session_state para não perder no refresh
            foto = st.camera_input(f"Capturar evidência do Item {i+1}", key=f"cam_{i}")
            
            if foto:
                st.session_state.fotos[i] = foto
                st.success(f"Foto do item {i+1} capturada!")

            conferencias.append({
                "item": item,
                "status": "CONFORME" if status_ok else "PENDENTE",
                "foto": st.session_state.fotos.get(i)
            })

    # --- GERAR PDF ---
    st.divider()
    if st.button("🚀 Finalizar e Gerar Relatório PDF"):
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(190, 10, "RELATORIO DE CONFORMIDADE TECNICA", ln=True, align='C')
            
            pdf.set_font("Arial", size=10)
            pdf.cell(190, 8, f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
            pdf.cell(190, 8, f"ARP: {arp} | FORNECEDOR: {fornecedor}", ln=True)
            pdf.cell(190, 8, f"OBJETO: {objeto}", ln=True)
            pdf.ln(5)

            for idx, c in enumerate(conferencias):
                # Limpeza de texto para PDF
                txt = c['item'].encode('latin-1', 'ignore').decode('latin-1')
                pdf.set_font("Arial", 'B', 10)
                pdf.multi_cell(190, 7, f"{idx+1}. {txt}")
                pdf.set_font("Arial", size=10)
                pdf.cell(190, 7, f"STATUS: {c['status']}", ln=True)
                
                if c['foto'] is not None:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(c['foto'].getvalue())
                        tmp_path = tmp.name
                    
                    # Se a foto for ocupar muito espaço, pula página
                    if pdf.get_y() > 210:
                        pdf.add_page()
                    
                    pdf.image(tmp_path, x=10, w=60)
                    pdf.ln(2)
                    os.unlink(tmp_path)
                
                pdf.ln(4)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(4)

            pdf_bytes = pdf.output(dest='S').encode('latin-1', errors='replace')
            st.download_button("📥 Baixar PDF Agora", data=pdf_bytes, file_name="Relatorio_Tecnico.pdf")
            
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")

# BOTÃO DE REINICIAR
if st.sidebar.button("Limpar Tudo"):
    st.session_state.checklist_items = []
    st.session_state.fotos = {}
    st.rerun()