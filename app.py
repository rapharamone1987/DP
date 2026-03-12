import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import json

# --- CONFIGURAÇÃO DA IA ---
if "GOOGLE_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GOOGLE_API_KEY"]
else:
    CHAVE_API = ""

@st.cache_resource
def carregar_modelo_seguro(api_key):
    try:
        genai.configure(api_key=api_key.strip())
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        preferencia = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        selecionado = next((p for p in preferencia if p in modelos), modelos[0])
        return genai.GenerativeModel(selecionado), selecionado
    except Exception as e:
        return None, str(e)

# --- FUNÇÃO DE LIMPEZA DE DADOS (Evita Dicionários no Texto) ---
def limpar_valor(valor):
    if isinstance(valor, dict):
        return str(next(iter(valor.values())))
    return str(valor)

# --- LAYOUT E CSS ---
st.set_page_config(page_title="Checklist Técnico", layout="centered")
st.markdown("""
    <style>
    .titulo-verde { color: #009A44; font-weight: bold; font-size: 24px; text-transform: uppercase; text-align: center; }
    .caixa-info { background-color: #F8F9FA; padding: 15px; border-radius: 8px; border: 1px solid #DEE2E6; margin-bottom: 20px; }
    .barra-secao { background-color: #009A44; color: white; padding: 8px 15px; font-weight: bold; border-radius: 4px; margin: 20px 0; }
    </style>
    """, unsafe_allow_html=True)

# --- ESTADO DA SESSÃO ---
if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "observacoes" not in st.session_state: st.session_state.observacoes = {}
if "dados_auto" not in st.session_state: 
    st.session_state.dados_auto = {"fornecedor": "", "edital": "", "processo": "", "objeto": "", "centro_custo": ""}

# --- PROCESSAMENTO ---
model, _ = carregar_modelo_seguro(CHAVE_API)

st.markdown('<p class="titulo-verde">📋 Checklist de Recebimento</p>', unsafe_allow_html=True)
pdf_file = st.file_uploader("Upload do TR", type="pdf")

if pdf_file and not st.session_state.checklist_items:
    with st.spinner("Extraindo dados técnicos..."):
        try:
            pdf_data = pdf_file.read()
            prompt = """Retorne APENAS um JSON (texto simples nos valores):
            {"fornecedor": "string", "edital": "string", "processo": "string", "objeto": "string", "centro_custo": "string", "checklist": ["item1", "item2"]}"""
            response = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_data}, prompt])
            data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
            
            st.session_state.dados_auto = {k: limpar_valor(v) for k, v in data.items() if k != 'checklist'}
            st.session_state.checklist_items = data.get("checklist", [])
            st.rerun()
        except Exception as e:
            st.error(f"Erro na extração: {e}")

# --- FORMULÁRIO CABEÇALHO ---
if st.session_state.checklist_items:
    st.markdown(f'<p class="titulo-verde">{st.session_state.dados_auto["objeto"].upper()}</p>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="caixa-info">', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        edital = c1.text_input("Edital:", value=st.session_state.dados_auto["edital"])
        processo = c2.text_input("Processo:", value=st.session_state.dados_auto["processo"])
        fornecedor = c1.text_input("Fornecedor:", value=st.session_state.dados_auto["fornecedor"])
        placa = c2.text_input("Placa / ID do Bem:")
        
        natureza = st.radio("Natureza do Bem:", ["Consumo", "Permanente"], horizontal=True)
        centro_custo = ""
        if natureza == "Permanente":
            centro_custo = st.text_input("Centro de Custo:", value=st.session_state.dados_auto["centro_custo"])
        st.markdown('</div>', unsafe_allow_html=True)

    # --- ITENS ---
    st.markdown('<div class="barra-secao">1. MECÂNICA E ITENS TÉCNICOS</div>', unsafe_allow_html=True)
    
    todos_ok = True
    for i, item in enumerate(st.session_state.checklist_items):
        with st.container(border=True):
            col_check, col_texto = st.columns([0.1, 0.9])
            st.session_state.conferidos[i] = col_check.checkbox("OK", key=f"c_{i}")
            if not st.session_state.conferidos[i]: todos_ok = False
            
            col_texto.write(f"**{item}**")
            foto = st.camera_input(f"Foto Item {i+1}", key=f"f_{i}")
            if foto: st.session_state.fotos[i] = foto
            
            if not st.session_state.conferidos[i]:
                st.session_state.observacoes[i] = st.text_area(f"Pendência/OBS Item {i+1}", key=f"obs_{i}")

    # --- DADOS DO SERVIDOR (FINAL) ---
    st.markdown('<div class="barra-secao">2. IDENTIFICAÇÃO DO SERVIDOR</div>', unsafe_allow_html=True)
    servidor_nome = st.text_input("Nome Completo do Servidor:")
    servidor_id = st.text_input("Matrícula / ID:")

    # --- GERAR PDF ---
    if st.button("🚀 GERAR RELATÓRIO FINAL"):
        try:
            pdf = FPDF()
            pdf.set_margins(15, 15, 15)
            pdf.add_page()
            
            # Título e Cabeçalho
            pdf.set_font("Arial", 'B', 14)
            pdf.set_text_color(0, 154, 68)
            pdf.multi_cell(180, 8, f"CHECKLIST DE RECEBIMENTO TECNICO - {st.session_state.dados_auto['objeto'].upper()}", align='C')
            pdf.ln(5)
            
            pdf.set_font("Arial", 'B', 9)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(180, 7, f"EDITAL: {edital} | PROCESSO: {processo}", ln=True, border='B')
            pdf.ln(2)
            
            # Tabela de Dados (Simples para não estourar margem)
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(90, 8, f"FORNECEDOR: {fornecedor[:45]}", border=0)
            pdf.cell(90, 8, f"PLACA: {placa}", ln=True, border=0)
            if natureza == "Permanente":
                pdf.cell(180, 8, f"CENTRO DE CUSTO: {centro_custo}", ln=True, border=0)
            pdf.ln(5)

            # Título Seção
            pdf.set_fill_color(0, 154, 68)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(180, 8, " 1. MECANICA E ITENS TECNICOS", ln=True, fill=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)

            # Itens e Fotos
            for idx, item_txt in enumerate(st.session_state.checklist_items):
                status = "[OK]" if st.session_state.conferidos.get(idx) else "[PENDENTE]"
                pdf.set_font("Arial", 'B', 10)
                pdf.multi_cell(180, 7, f"{status} - {item_txt.encode('latin-1','ignore').decode('latin-1')}")
                
                if not st.session_state.conferidos.get(idx):
                    pdf.set_font("Arial", 'I', 9)
                    pdf.set_text_color(200, 0, 0)
                    pdf.multi_cell(170, 6, f"     OBS: {st.session_state.observacoes.get(idx, 'Não informada')}")
                    pdf.set_text_color(0, 0, 0)

                if idx in st.session_state.fotos:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(st.session_state.fotos[idx].getvalue())
                        tmp_path = tmp.name
                    if pdf.get_y() > 200: pdf.add_page()
                    pdf.image(tmp_path, x=20, w=150) # Foto Grande Centralizada
                    pdf.ln(5)
                    os.unlink(tmp_path)
                pdf.ln(2)

            # --- ATESTO FINAL ---
            pdf.ln(10)
            if todos_ok:
                pdf.set_fill_color(240, 240, 240)
                pdf.set_font("Arial", 'B', 10)
                if natureza == "Permanente":
                    texto = "ATESTO O RECEBIMENTO PROVISORIO do(s) bem(ns), conforme Art. 140, I, 'a' da Lei 14.133/21, para posterior verificacao de conformidade tecnica."
                else:
                    texto = "ATESTO O RECEBIMENTO DEFINITIVO dos materiais, por estarem em total conformidade com as especificacoes."
                pdf.multi_cell(180, 8, texto, border=1, align='C', fill=True)
            else:
                pdf.set_font("Arial", 'B', 10)
                pdf.set_text_color(200, 0, 0)
                pdf.multi_cell(180, 8, "DOCUMENTO ENCERRADO COM PENDENCIAS. O ATESTO NAO FOI REALIZADO.", border=1, align='C')
                pdf.set_text_color(0, 0, 0)

            # Rodapé Servidor
            pdf.ln(20)
            pdf.cell(180, 6, f"SERVIDOR: {servidor_nome.upper()} (ID: {servidor_id})", ln=True, align='C')
            pdf.set_font("Arial", 'I', 7)
            pdf.cell(180, 6, f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')

            pdf_out = pdf.output(dest='S').encode('latin-1', errors='replace')
            st.download_button("📥 Baixar PDF", data=pdf_out, file_name=f"Relatorio_{fornecedor}.pdf")
            
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")

if st.sidebar.button("Limpar e Iniciar Novo"):
    st.session_state.clear()
    st.rerun()

