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
    CHAVE_API = ""

@st.cache_resource
def carregar_modelo_seguro(api_key):
    try:
        genai.configure(api_key=api_key.strip())
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        selecionado = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in modelos else modelos[0]
        return genai.GenerativeModel(
            model_name=selecionado,
            system_instruction="Você é um Engenheiro de Recebimento. Liste apenas componentes físicos. Delete cláusulas jurídicas."
        ), selecionado
    except Exception as e:
        return None, str(e)

# --- 2. FUNÇÃO PARA DESENHAR O ÍCONE NO PDF ---
def desenhar_icone_check(pdf, x, y, status):
    if status: # CIRCULO VERDE COM CHECK BRANCO
        pdf.set_fill_color(0, 154, 68)
        pdf.set_draw_color(0, 154, 68)
        pdf.ellipse(x, y, 5, 5, 'F')
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.4)
        pdf.line(x+1.2, y+2.5, x+2.2, y+3.8)
        pdf.line(x+2.2, y+3.8, x+3.8, y+1.5)
    else: # CIRCULO VERMELHO COM X BRANCO
        pdf.set_fill_color(200, 0, 0)
        pdf.set_draw_color(200, 0, 0)
        pdf.ellipse(x, y, 5, 5, 'F')
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.4)
        pdf.line(x+1.5, y+1.5, x+3.5, y+3.5)
        pdf.line(x+3.5, y+1.5, x+1.5, y+3.5)
    pdf.set_line_width(0.2)
    pdf.set_draw_color(0, 0, 0)

# --- 3. INTERFACE STREAMLIT ---
st.set_page_config(page_title="Checklist Técnico", layout="centered")
st.markdown("""<style>
    .titulo-verde { color: #009A44; font-weight: bold; font-size: 22px; text-transform: uppercase; text-align: center; }
    .caixa-info { background-color: #F8F9FA; padding: 15px; border-radius: 8px; border: 1px solid #DEE2E6; }
    .barra-secao { background-color: #009A44; color: white; padding: 8px 15px; font-weight: bold; border-radius: 4px; margin: 20px 0; }
</style>""", unsafe_allow_html=True)

if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "dados_auto" not in st.session_state: 
    st.session_state.dados_auto = {"fornecedor": "", "edital": "", "objeto": "", "centro_custo": ""}

model, _ = carregar_modelo_seguro(CHAVE_API)

st.markdown('<p class="titulo-verde">📋 Recebimento Técnico</p>', unsafe_allow_html=True)
pdf_file = st.file_uploader("Upload do TR (PDF)", type="pdf")

if pdf_file and not st.session_state.checklist_items:
    with st.spinner("Extraindo dados técnicos..."):
        try:
            pdf_data = pdf_file.read()
            prompt = """Retorne um JSON estrito com: fornecedor, edital, objeto, centro_custo e checklist (apenas itens físicos)."""
            response = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_data}, prompt])
            data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
            st.session_state.dados_auto = {k: str(v) for k, v in data.items() if k != 'checklist'}
            st.session_state.checklist_items = data.get("checklist", [])
            st.rerun()
        except Exception as e:
            st.error(f"Erro na análise: {e}")

if st.session_state.checklist_items:
    # Título curto (5 palavras)
    obj_curto = " ".join(st.session_state.dados_auto["objeto"].split()[:5])
    st.markdown(f'<p class="titulo-verde">CHECKLIST: {obj_curto.upper()}</p>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="caixa-info">', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        edital = c1.text_input("Edital/ARP:", value=st.session_state.dados_auto["edital"])
        fornecedor = c2.text_input("Fornecedor:", value=st.session_state.dados_auto["fornecedor"])
        placa = c1.text_input("Placa / ID:")
        natureza = c2.radio("Natureza:", ["Consumo", "Permanente"], horizontal=True)
        centro_custo = st.text_input("Centro de Custo:", value=st.session_state.dados_auto["centro_custo"]) if natureza == "Permanente" else ""
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="barra-secao">1. CONFERÊNCIA TÉCNICA</div>', unsafe_allow_html=True)
    
    todos_ok = True
    for i, item in enumerate(st.session_state.checklist_items):
        with st.container(border=True):
            c_check, c_text = st.columns([0.15, 0.85])
            st.session_state.conferidos[i] = c_check.checkbox("OK", key=f"c_{i}")
            if not st.session_state.conferidos[i]: todos_ok = False
            c_text.write(f"**{item}**")
            
            # CÂMERA TRASEIRA (Aparece para o usuário preencher)
            foto = st.camera_input(f"Foto Item {i+1}", key=f"f_{i}", facing_mode="environment")
            if foto: st.session_state.fotos[i] = foto

    obs_geral = ""
    if not todos_ok:
        st.warning("⚠️ Pendências detectadas:")
        obs_geral = st.text_area("Descreva as pendências:")

    serv_nome = st.text_input("Servidor Responsável:")

    # --- 4. GERAÇÃO DO PDF ---
    if st.button("🚀 GERAR RELATÓRIO PDF"):
        if not serv_nome:
            st.error("Informe o nome do servidor.")
        else:
            try:
                pdf = FPDF()
                pdf.set_margins(20, 20, 20)
                pdf.add_page()
                pdf.set_font("Arial", 'B', 14)
                pdf.set_text_color(0, 154, 68)
                pdf.multi_cell(170, 10, f"CHECKLIST - {obj_curto.upper()}", align='C')
                pdf.ln(5)
                
                pdf.set_font("Arial", 'B', 10); pdf.set_text_color(0, 0, 0)
                pdf.cell(170, 8, f"EDITAL/ARP: {edital}", ln=True, border='B')
                pdf.write(8, "FORNECEDOR: "); pdf.set_font("Arial", '', 10)
                pdf.multi_cell(140, 8, fornecedor.upper())
                pdf.set_font("Arial", 'B', 10); pdf.cell(170, 8, f"PLACA / ID: {placa.upper()}", ln=True)
                if centro_custo:
                    pdf.write(8, "C. CUSTO: "); pdf.set_font("Arial", '', 10)
                    pdf.multi_cell(140, 8, centro_custo.upper())
                
                pdf.ln(5)
                pdf.set_fill_color(0, 154, 68); pdf.set_text_color(255, 255, 255)
                pdf.cell(170, 10, " 1. ITENS CONFERIDOS", ln=True, fill=True)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(3)

                for idx, item_txt in enumerate(st.session_state.checklist_items):
                    status = st.session_state.conferidos.get(idx, False)
                    y_at = pdf.get_y()
                    desenhar_icone_check(pdf, 22, y_at + 1, status)
                    
                    pdf.set_font("Arial", 'B', 10)
                    pdf.set_x(28)
                    pdf.multi_cell(160, 7, item_txt.encode('latin-1','replace').decode('latin-1'))

                    if idx in st.session_state.fotos:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(st.session_state.fotos[idx].getvalue())
                            tmp_path = tmp.name
                        if pdf.get_y() > 180: pdf.add_page()
                        pdf.image(tmp_path, x=35, w=135); pdf.ln(5)
                        os.unlink(tmp_path)
                    pdf.ln(2)

                pdf.ln(10)
                if todos_ok:
                    pdf.set_fill_color(245, 245, 245); pdf.set_font("Arial", 'B', 10)
                    t = "ATESTO O RECEBIMENTO DEFINITIVO" if natureza == "Consumo" else "ATESTO O RECEBIMENTO PROVISORIO"
                    pdf.multi_cell(170, 10, f"{t} do objeto.", border=1, align='C', fill=True)
                else:
                    pdf.set_font("Arial", 'B', 10); pdf.set_text_color(200, 0, 0)
                    pdf.multi_cell(170, 8, f"PENDENCIAS:\n{obs_geral}", border=1, align='L')
                
                pdf.ln(25); pdf.set_text_color(0, 0, 0)
                pdf.cell(170, 8, "________________________________________________", ln=True, align='C')
                pdf.cell(170, 6, f"SERVIDOR: {serv_nome.upper()}", ln=True, align='C')
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1', errors='replace')
                st.download_button("📥 Baixar PDF", data=pdf_bytes, file_name="Checklist.pdf")
            except Exception as e:
                st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Nova Inspeção"):
    st.session_state.clear(); st.rerun()





