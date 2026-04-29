import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import json
import time
import re

# --- 1. CONFIGURAÇÃO DA IA ---
if "GOOGLE_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GOOGLE_API_KEY"]
else:
    CHAVE_API = "" 

@st.cache_resource
def inicializar_ia(api_key):
    try:
        genai.configure(api_key=api_key.strip())
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        selecionado = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in modelos else modelos[0]
        
        # --- SEU PROMPT ORIGINAL (SINTAXE CORRIGIDA) ---
        prompt_sistema = (
            "Você é um Especialista em Recebimento de bens e materiais no setor público. "
            "Pergunte se o recebimento é Provisório ou Definitivo, se definitivo Liste os detalhes que devem ser conferidos, "
            "conforme o tipo de item a receber (mARCA, MODELO, Peças, cores, medidas, se está ligando, nível de óleo, Hardware, Pintura), "
            "se provisório, a conferencia é simplificada (MARCA/MODELO, COR, QUANTIDADE, VOLTAGEM, ETC). "
            "Ignore cláusulas jurídicas, prazos, etc, NÃO CRIE ITENS DE CHECK GENERICOS" 
        )
        
        return genai.GenerativeModel(model_name=selecionado, system_instruction=prompt_sistema)
    except:
        return None

model = inicializar_ia(CHAVE_API)

# --- 2. FUNÇÕES DE SUPORTE ---
def extrair_texto_flexivel(texto):
    dados = {"fornecedor": "", "edital": "", "objeto": "", "checklist": []}
    linhas = texto.split('\n')
    for linha in linhas:
        l = linha.strip()
        if not l: continue
        if "FORNECEDOR:" in l.upper(): dados["fornecedor"] = l.split(":", 1)[1].strip()
        elif "EDITAL:" in l.upper() or "ARP:" in l.upper(): dados["edital"] = l.split(":", 1)[1].strip()
        elif "OBJETO:" in l.upper(): dados["objeto"] = l.split(":", 1)[1].strip()
        elif l.startswith(("-", "*", "•")) or (len(l) > 5 and l[0].isdigit() and "." in l[:3]):
            item = re.sub(r'^[-*•0-9.\s]+', '', l)
            if len(item) > 3: dados["checklist"].append(item)
    return dados

def desenhar_check(pdf, x, y, status):
    if status:
        pdf.set_fill_color(0, 154, 68); pdf.ellipse(x, y, 5, 5, 'F')
        pdf.set_draw_color(255, 255, 255); pdf.set_line_width(0.4)
        pdf.line(x+1.2, y+2.5, x+2.2, y+3.8); pdf.line(x+2.2, y+3.8, x+3.8, y+1.5)
    else:
        pdf.set_fill_color(200, 0, 0); pdf.ellipse(x, y, 5, 5, 'F')
        pdf.set_draw_color(255, 255, 255); pdf.set_line_width(0.4)
        pdf.line(x+1.5, y+1.5, x+3.5, y+3.5); pdf.line(x+3.5, y+1.5, x+1.5, y+3.5)
    pdf.set_line_width(0.2); pdf.set_draw_color(0, 0, 0)

# --- 3. INTERFACE ---
st.set_page_config(page_title="Checklist IA", layout="centered")
st.markdown("<style>.titulo-verde { color: #009A44; font-weight: bold; font-size: 22px; text-transform: uppercase; text-align: center; } .caixa { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #ddd; } .barra { background-color: #009A44; color: white; padding: 8px; font-weight: bold; border-radius: 5px; }</style>", unsafe_allow_html=True)

if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "dados_auto" not in st.session_state: st.session_state.dados_auto = {}
if "item_da_foto" not in st.session_state: st.session_state.item_da_foto = None

st.markdown('<p class="titulo-verde">📋 Recebimento Técnico Inteligente</p>', unsafe_allow_html=True)

# --- 4. CARGA DE DADOS ---
if not st.session_state.checklist_items:
    pdf_file = st.file_uploader("Suba o PDF do TR ou Empenho", type="pdf")
    if pdf_file:
        col1, col2 = st.columns(2)
        if col1.button("🔍 ANALISAR COM IA"):
            with st.spinner("IA processando..."):
                try:
                    prompt = "Extraia Fornecedor, Edital, Objeto e crie um CHECKLIST (use - para itens)."
                    res = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_file.read()}, prompt])
                    dados = extrair_texto_flexivel(res.text)
                    st.session_state.dados_auto = dados
                    st.session_state.checklist_items = dados["checklist"]
                    st.rerun()
                except Exception as e:
                    if "429" in str(e): st.error("Cota diária atingida. Use o Modo Manual abaixo.")
                    else: st.error(f"Erro: {e}")
        
        if col2.button("📝 MODO MANUAL"):
            st.session_state.modo_manual = True

    if st.session_state.get("modo_manual"):
        texto_manual = st.text_area("Cole o texto da IA aqui:")
        if st.button("Carregar Dados"):
            dados = extrair_texto_flexivel(texto_manual)
            st.session_state.dados_auto = dados
            st.session_state.checklist_items = dados["checklist"]
            st.rerun()

# --- 5. FORMULÁRIO E ITENS ---
if st.session_state.checklist_items:
    obj_nome = st.session_state.dados_auto.get("objeto", "RECEBIMENTO")
    obj_curto = " ".join(obj_nome.split()[:5]).upper()
    st.markdown(f'<p class="titulo-verde">CONFERÊNCIA: {obj_curto}</p>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="caixa">', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        edital = c1.text_input("Edital/ARP:", value=st.session_state.dados_auto.get("edital", ""))
        fornecedor = c2.text_input("Fornecedor:", value=st.session_state.dados_auto.get("fornecedor", ""))
        placa = c1.text_input("Placa / ID:")
        natureza = c2.radio("Recebimento:", ["Consumo (Definitivo)", "Permanente (Provisório)"], horizontal=True)
        centro_custo = st.text_input("Centro de Custo:") if "Permanente" in natureza else ""
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="barra">1. ITENS TÉCNICOS</div>', unsafe_allow_html=True)
    
    todos_ok = True
    for i, item in enumerate(st.session_state.checklist_items):
        with st.container(border=True):
            col_ch, col_tx = st.columns([0.15, 0.85])
            st.session_state.conferidos[i] = col_ch.checkbox("OK", key=f"c_{i}")
            if not st.session_state.conferidos[i]: todos_ok = False
            col_tx.write(f"**{item}**")
            
            if st.session_state.item_da_foto == i:
                foto = st.camera_input(f"Foto {i+1}", key=f"f_{i}")
                if foto:
                    st.session_state.fotos[i] = foto
                    if st.button(f"✅ Salvar Foto {i+1}", key=f"s_{i}"):
                        st.session_state.item_da_foto = None; st.rerun()
            else:
                c_bt, c_pv = st.columns([0.4, 0.6])
                if c_bt.button("📸 Câmera", key=f"btn_{i}"):
                    st.session_state.item_da_foto = i; st.rerun()
                if i in st.session_state.fotos: c_pv.image(st.session_state.fotos[i], width=100)

    obs_geral = st.text_area("⚠️ Descreva as Pendências:") if not todos_ok else ""
    servidor = st.text_input("Servidor Responsável pelo Atesto:")

    if st.button("🚀 GERAR PDF FINAL"):
        if not servidor: st.error("Informe o servidor.")
        else:
            try:
                pdf = FPDF(); pdf.set_margins(20, 20, 20); pdf.add_page()
                pdf.set_font("Arial", 'B', 14); pdf.set_text_color(0, 154, 68)
                pdf.multi_cell(170, 10, f"RELATORIO - {obj_curto}", align='C')
                pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.set_text_color(0, 0, 0)
                pdf.cell(170, 8, f"EDITAL: {edital}", ln=True, border='B')
                pdf.write(8, "FORNECEDOR: "); pdf.multi_cell(140, 8, fornecedor.upper())
                pdf.set_font("Arial", 'B', 10); pdf.cell(170, 8, f"PLACA: {placa.upper()}", ln=True)
                if centro_custo: pdf.write(8, "C. CUSTO: "); pdf.multi_cell(140, 8, centro_custo.upper())
                
                pdf.ln(5); pdf.set_fill_color(0, 154, 68); pdf.set_text_color(255, 255, 255)
                pdf.cell(170, 10, " 1. CONFERENCIA REALIZADA", ln=True, fill=True)
                pdf.set_text_color(0, 0, 0); pdf.ln(3)

                for idx, item_txt in enumerate(st.session_state.checklist_items):
                    desenhar_check(pdf, 22, pdf.get_y()+1, st.session_state.conferidos.get(idx))
                    pdf.set_x(28); pdf.set_font("Arial", 'B', 10)
                    pdf.multi_cell(160, 7, item_txt.encode('latin-1','replace').decode('latin-1'))
                    if idx in st.session_state.fotos:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(st.session_state.fotos[idx].getvalue()); tmp_path = tmp.name
                        if pdf.get_y() > 180: pdf.add_page()
                        pdf.image(tmp_path, x=35, w=130); pdf.ln(5); os.unlink(tmp_path)
                    pdf.ln(2)

                pdf.ln(10)
                if todos_ok:
                    pdf.set_fill_color(245, 245, 245); pdf.set_font("Arial", 'B', 10)
                    t = "RECEBIMENTO DEFINITIVO" if "Consumo" in natureza else "RECEBIMENTO PROVISORIO"
                    pdf.multi_cell(170, 10, f"ATESTO O {t} DO OBJETO POR ESTAR EM CONFORMIDADE TECNICA.", border=1, align='C', fill=True)
                else:
                    pdf.set_font("Arial", 'B', 10); pdf.set_text_color(200, 0, 0)
                    pdf.multi_cell(170, 8, f"PENDENCIAS DETECTADAS:\n{obs_geral}", border=1)

                pdf.ln(20); pdf.set_text_color(0, 0, 0)
                pdf.cell(170, 8, "________________________________________", ln=True, align='C')
                pdf.cell(170, 6, f"SERVIDOR: {servidor.upper()}", ln=True, align='C')
                st.download_button("📥 Baixar PDF", data=pdf.output(dest='S').encode('latin-1','replace'), file_name="Checklist.pdf")
            except Exception as e: st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Reiniciar"):
    st.session_state.clear()
    st.rerun()
