import streamlit as st
import time
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import re

# --- 1. CONFIGURAÇÃO DA IA ---
if "GOOGLE_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GOOGLE_API_KEY"]
else:
    CHAVE_API = ""

@st.cache_resource
def carregar_modelo(api_key):
    try:
        genai.configure(api_key=api_key.strip())
        return genai.GenerativeModel(model_name='gemini-1.5-flash')
    except: return None

model = carregar_modelo(CHAVE_API)

# --- 2. INICIALIZAÇÃO DO ESTADO ---
if "dados_prontos" not in st.session_state: st.session_state.dados_prontos = False
if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "dados_auto" not in st.session_state: 
    st.session_state.dados_auto = {"fornecedor": "", "edital": "", "objeto": "", "centro_custo": ""}
if "item_da_foto" not in st.session_state: st.session_state.item_da_foto = None

# --- 3. FUNÇÃO DE PARSER DE TEXTO (A MÁGICA) ---
def extrair_do_texto_puro(texto):
    """Lê o texto e extrai os campos baseado em palavras-chave"""
    dados = {"fornecedor": "", "edital": "", "objeto": "", "checklist": []}
    
    linhas = texto.split('\n')
    capturando_checklist = False
    
    for linha in linhas:
        l = linha.strip()
        if not l: continue
        
        # Identifica Cabeçalho
        if "FORNECEDOR:" in l.upper(): dados["fornecedor"] = l.split(":", 1)[1].strip()
        elif "EDITAL:" in l.upper() or "EMPENHO:" in l.upper(): dados["edital"] = l.split(":", 1)[1].strip()
        elif "OBJETO:" in l.upper(): dados["objeto"] = l.split(":", 1)[1].strip()
        
        # Identifica Início do Checklist
        elif "CHECKLIST:" in l.upper() or "ITENS:" in l.upper():
            capturando_checklist = True
        
        # Captura itens (linhas que começam com - ou *)
        elif capturando_checklist and (l.startswith("-") or l.startswith("*") or l[0].isdigit()):
            item = re.sub(r'^[-*0-9.\s]+', '', l) # Limpa números e traços do início
            if len(item) > 3: dados["checklist"].append(item)
            
    return dados

# --- 4. INTERFACE ---
st.set_page_config(page_title="Checklist Técnico", layout="centered")
st.markdown("<style>.titulo-verde { color: #009A44; font-weight: bold; font-size: 22px; text-transform: uppercase; text-align: center; } .caixa-info { background-color: #F8F9FA; padding: 15px; border-radius: 8px; border: 1px solid #DEE2E6; margin-bottom: 20px; } .barra-secao { background-color: #009A44; color: white; padding: 8px 15px; font-weight: bold; border-radius: 4px; margin: 20px 0; }</style>", unsafe_allow_html=True)

st.markdown('<p class="titulo-verde">📋 Recebimento Técnico</p>', unsafe_allow_html=True)

if not st.session_state.dados_prontos:
    modo = st.radio("Como carregar os dados?", ["Analisar PDF (IA)", "Colar Texto do Gemini"], horizontal=True)
    
    if modo == "Analisar PDF (IA)":
        pdf_file = st.file_uploader("Suba o PDF do TR ou Empenho", type="pdf")
        if st.button("🔍 Iniciar Análise Automática"):
            if pdf_file:
                with st.spinner("IA Extraindo dados..."):
                    try:
                        prompt = "Analise o TR e extraia neste formato: FORNECEDOR: [nome], EDITAL: [numero], OBJETO: [nome]. Abaixo, liste os itens técnicos em CHECKLIST: (use - para cada item)."
                        response = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_file.read()}, prompt])
                        dados = extrair_do_texto_puro(response.text)
                        st.session_state.dados_auto = dados
                        st.session_state.checklist_items = dados["checklist"]
                        st.session_state.dados_prontos = True
                        st.rerun()
                    except: st.error("Erro de cota. Tente o modo 'Colar Texto'.")
    else:
        st.info("💡 Vá ao Gemini, anexe o PDF e peça: 'Extraia Fornecedor, Edital, Objeto e os itens de conferência técnica'. Depois cole o texto aqui:")
        texto_colado = st.text_area("Cole o texto aqui:", height=200)
        if st.button("Carregar Dados"):
            dados = extrair_do_texto_puro(texto_colado)
            st.session_state.dados_auto = dados
            st.session_state.checklist_items = dados["checklist"]
            st.session_state.dados_prontos = True
            st.rerun()

# --- 5. FORMULÁRIO E CHECKLIST ---
if st.session_state.dados_prontos:
    obj_curto = " ".join(st.session_state.dados_auto["objeto"].split()[:5])
    st.markdown(f'<p class="titulo-verde">CHECKLIST: {obj_curto.upper()}</p>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="caixa-info">', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        edital = c1.text_input("Edital/Empenho:", value=st.session_state.dados_auto["edital"])
        fornecedor = c2.text_input("Fornecedor:", value=st.session_state.dados_auto["fornecedor"])
        natureza = c2.radio("Natureza:", ["Consumo", "Permanente"], horizontal=True)
        centro_custo = st.text_input("Centro de Custo:", value=st.session_state.dados_auto.get("centro_custo", "")) if natureza == "Permanente" else ""
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="barra-secao">1. CONFERÊNCIA TÉCNICA</div>', unsafe_allow_html=True)
    
    todos_ok = True
    for i, item in enumerate(st.session_state.checklist_items):
        with st.container(border=True):
            col1, col2 = st.columns([0.2, 0.8])
            st.session_state.conferidos[i] = col1.checkbox("OK", key=f"c_{i}")
            if not st.session_state.conferidos[i]: todos_ok = False
            col2.write(f"**{item}**")
            
            if st.session_state.item_da_foto == i:
                foto = st.camera_input(f"Foto {i+1}", key=f"f_{i}")
                if foto: 
                    st.session_state.fotos[i] = foto
                    if st.button(f"Salvar Foto {i+1}"): 
                        st.session_state.item_da_foto = None
                        st.rerun()
            else:
                c_btn, c_prev = st.columns([0.4, 0.6])
                if c_btn.button(f"📸 Câmera", key=f"b_{i}"): 
                    st.session_state.item_da_foto = i
                    st.rerun()
                if i in st.session_state.fotos: 
                    c_prev.image(st.session_state.fotos[i], width=100)

    obs_geral = "" if todos_ok else st.text_area("Descreva as pendências:")
    serv_nome = st.text_input("Nome do Servidor (Atestante):")

    if st.button("🚀 GERAR PDF FINAL"):
        if not serv_nome: st.error("Nome do servidor obrigatório.")
        else:
            try:
                pdf = FPDF(); pdf.set_margins(20, 20, 20); pdf.add_page()
                pdf.set_font("Arial", 'B', 14); pdf.set_text_color(0, 154, 68)
                pdf.multi_cell(170, 10, "RELATORIO DE RECEBIMENTO TECNICO", align='C')
                pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.set_text_color(0, 0, 0)
                pdf.cell(170, 8, f"EMPENHO: {edital}", ln=True, border='B')
                pdf.write(8, "FORNECEDOR: "); pdf.multi_cell(140, 8, fornecedor.upper())
                pdf.ln(5); pdf.set_fill_color(0, 154, 68); pdf.set_text_color(255, 255, 255)
                pdf.cell(170, 10, " ITENS CONFERIDOS", ln=True, fill=True)
                pdf.set_text_color(0, 0, 0); pdf.ln(3)

                for idx, item_txt in enumerate(st.session_state.checklist_items):
                    y_at = pdf.get_y()
                    # Função de ícone aqui (desenhar_icone_check) - simplificado para o exemplo
                    pdf.set_font("Arial", 'B', 10); pdf.multi_cell(170, 7, f"{'[OK]' if st.session_state.conferidos.get(idx) else '[P]'} {item_txt.encode('latin-1','replace').decode('latin-1')}")
                    if idx in st.session_state.fotos:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(st.session_state.fotos[idx].getvalue()); tmp_path = tmp.name
                        if pdf.get_y() > 180: pdf.add_page()
                        pdf.image(tmp_path, x=35, w=130); pdf.ln(5); os.unlink(tmp_path)
                
                pdf.ln(10)
                atesto = "RECEBIMENTO DEFINITIVO" if natureza == "Consumo" else "RECEBIMENTO PROVISORIO"
                pdf.multi_cell(170, 10, f"ATESTO O {atesto} POR CONFORMIDADE." if todos_ok else f"PENDENCIAS: {obs_geral}", border=1, align='C')
                pdf.ln(20); pdf.cell(170, 8, "________________________________________", ln=True, align='C')
                pdf.cell(170, 6, f"SERVIDOR: {serv_nome.upper()}", ln=True, align='C')
                st.download_button("📥 Baixar PDF", data=pdf.output(dest='S').encode('latin-1','replace'), file_name="Checklist.pdf")
            except Exception as e: st.error(f"Erro: {e}")

if st.sidebar.button("Nova Inspeção"): st.session_state.clear(); st.rerun()




