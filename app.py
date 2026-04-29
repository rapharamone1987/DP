import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import json
import time

# --- 1. CONFIGURAÇÃO DA IA ---
if "GOOGLE_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GOOGLE_API_KEY"]
else:
    CHAVE_API = "" # Para teste local

@st.cache_resource
def carregar_modelo(api_key):
    try:
        genai.configure(api_key=api_key.strip())
        # Usamos o 1.5-flash: é o mais rápido e com maior limite de cota
        return genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction="Você é um Engenheiro de Recebimento do Setor Público. Extraia Fornecedor, Edital/ARP e Objeto. No checklist, foque em itens físicos (Marca, Modelo, Estado, Funcionamento). Se for 'Provisório', seja sucinto. Se 'Definitivo', seja detalhado."
        )
    except: return None

model = carregar_modelo(CHAVE_API)

# --- 2. LOGICA DE INTELIGÊNCIA COM RETENTATIVA (PARA NÃO DAR ERRO DE COTA) ---
def analisar_pdf_com_ia(pdf_bytes):
    prompt = """Retorne APENAS um JSON estrito:
    {"fornecedor": "string", "edital": "string", "objeto": "string", "checklist": ["item1", "item2", "item3"]}"""
    
    for tentativa in range(3): # Tenta 3 vezes antes de desistir
        try:
            response = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_bytes}, prompt])
            return json.loads(response.text.replace("```json", "").replace("```", "").strip())
        except Exception as e:
            if "429" in str(e):
                time.sleep(5) # Espera 5 segundos e tenta de novo
                continue
            return str(e)
    return "Erro de cota persistente. Tente novamente em instantes."

# --- 3. FUNÇÕES DO PDF ---
def desenhar_check(pdf, x, y, status):
    pdf.set_fill_color(0, 154, 68) if status else pdf.set_fill_color(200, 0, 0)
    pdf.ellipse(x, y, 5, 5, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 8)
    pdf.text(x+1.5, y+3.8, "V" if status else "X")
    pdf.set_text_color(0, 0, 0)

# --- 4. INTERFACE ---
st.set_page_config(page_title="Checklist IA", layout="centered")
st.markdown("""<style>
    .titulo-verde { color: #009A44; font-weight: bold; font-size: 24px; text-transform: uppercase; text-align: center; }
    .caixa-info { background-color: #F8F9FA; padding: 15px; border-radius: 10px; border: 1px solid #DDD; margin-bottom: 20px; }
    .barra { background-color: #009A44; color: white; padding: 8px; font-weight: bold; border-radius: 5px; margin-bottom: 10px; }
</style>""", unsafe_allow_html=True)

if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "dados_auto" not in st.session_state: st.session_state.dados_auto = {}
if "item_da_foto" not in st.session_state: st.session_state.item_da_foto = None

st.markdown('<p class="titulo-verde">📋 Recebimento Técnico Inteligente</p>', unsafe_allow_html=True)

# Upload direto
pdf_file = st.file_uploader("Selecione o arquivo do Termo de Referência ou Empenho", type="pdf")

if pdf_file and not st.session_state.checklist_items:
    if st.button("🔍 ANALISAR AUTOMATICAMENTE", use_container_width=True):
        with st.spinner("A IA está lendo seu PDF e montando o checklist..."):
            resultado = analisar_pdf_com_ia(pdf_file.read())
            if isinstance(resultado, dict):
                st.session_state.dados_auto = resultado
                st.session_state.checklist_items = resultado.get("checklist", [])
                st.rerun()
            else:
                st.error(f"Erro na IA: {resultado}")

# --- 5. EXIBIÇÃO ---
if st.session_state.checklist_items:
    # Título encurtado (5 palavras)
    obj_nome = st.session_state.dados_auto.get("objeto", "RECEBIMENTO")
    titulo_curto = " ".join(obj_nome.split()[:5]).upper()
    st.markdown(f'<p class="titulo-verde">CONFERÊNCIA: {titulo_curto}</p>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="caixa-info">', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        edital = c1.text_input("Edital/ARP:", value=st.session_state.dados_auto.get("edital", ""))
        fornecedor = c2.text_input("Fornecedor:", value=st.session_state.dados_auto.get("fornecedor", ""))
        placa = c1.text_input("Placa / Patrimônio:")
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
            
            # Câmera Inteligente
            if st.session_state.item_da_foto == i:
                foto = st.camera_input(f"Capturar Foto {i+1}", key=f"f_{i}")
                if foto:
                    st.session_state.fotos[i] = foto
                    if st.button(f"✅ Salvar Foto {i+1}", key=f"s_{i}"):
                        st.session_state.item_da_foto = None; st.rerun()
            else:
                c_bt, c_pv = st.columns([0.4, 0.6])
                if i not in st.session_state.fotos:
                    if c_bt.button(f"📸 Abrir Câmera", key=f"btn_{i}"):
                        st.session_state.item_da_foto = i; st.rerun()
                else:
                    c_pv.image(st.session_state.fotos[i], width=100)
                    if c_bt.button(f"🔄 Trocar Foto", key=f"btn_{i}"):
                        st.session_state.item_da_foto = i; st.rerun()

    obs_geral = ""
    if not todos_ok:
        obs_geral = st.text_area("⚠️ Descreva as pendências:")

    servidor = st.text_input("Nome do Servidor (Atestante):")

    # --- 6. GERAÇÃO DO PDF ---
    if st.button("🚀 GERAR PDF FINAL"):
        if not servidor: st.error("Nome do servidor é obrigatório.")
        else:
            try:
                pdf = FPDF(); pdf.set_margins(20, 20, 20); pdf.add_page()
                pdf.set_font("Arial", 'B', 14); pdf.set_text_color(0, 154, 68)
                pdf.multi_cell(170, 10, f"RELATORIO - {titulo_curto}", align='C')
                pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.set_text_color(0, 0, 0)
                pdf.cell(170, 8, f"EDITAL: {edital}", ln=True, border='B')
                pdf.write(8, "FORNECEDOR: "); pdf.multi_cell(140, 8, fornecedor.upper())
                pdf.ln(5); pdf.set_fill_color(0, 154, 68); pdf.set_text_color(255, 255, 255)
                pdf.cell(170, 10, " 1. CONFERENCIA REALIZADA", ln=True, fill=True)
                pdf.set_text_color(0, 0, 0); pdf.ln(3)

                for idx, item_txt in enumerate(st.session_state.checklist_items):
                    y_at = pdf.get_y()
                    desenhar_check(pdf, 22, y_at+1, st.session_state.conferidos.get(idx))
                    pdf.set_x(28); pdf.set_font("Arial", 'B', 10)
                    pdf.multi_cell(160, 7, item_txt.encode('latin-1','replace').decode('latin-1'))
                    if idx in st.session_state.fotos:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(st.session_state.fotos[idx].getvalue()); tmp_path = tmp.name
                        if pdf.get_y() > 180: pdf.add_page()
                        pdf.image(tmp_path, x=35, w=130); pdf.ln(5); os.unlink(tmp_path)
                
                pdf.ln(10)
                if todos_ok:
                    pdf.set_fill_color(245, 245, 245); pdf.set_font("Arial", 'B', 10)
                    t = "RECEBIMENTO DEFINITIVO" if "Consumo" in natureza else "RECEBIMENTO PROVISORIO"
                    pdf.multi_cell(170, 10, f"ATESTO O {t} POR CONFORMIDADE TECNICA.", border=1, align='C', fill=True)
                else:
                    pdf.set_font("Arial", 'B', 10); pdf.set_text_color(200, 0, 0)
                    pdf.multi_cell(170, 8, f"PENDENCIAS: {obs_geral}", border=1)
                
                pdf.ln(20); pdf.set_text_color(0, 0, 0); pdf.cell(170, 8, "________________________________________", ln=True, align='C')
                pdf.cell(170, 6, f"SERVIDOR: {servidor.upper()}", ln=True, align='C')
                st.download_button("📥 Baixar PDF", data=pdf.output(dest='S').encode('latin-1','replace'), file_name="Checklist.pdf")
            except Exception as e: st.error(f"Erro: {e}")

if st.sidebar.button("Reiniciar"): st.session_state.clear(); st.rerun()

