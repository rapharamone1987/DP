import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import json
import time
import re
from PIL import Image

# --- CONFIGURAÇÃO DA IA ---
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
        prompt_base = "Você é um Especialista em Recebimento de bens públicos. Extraia Marca, Modelo e dados técnicos. Não use 'conforme'."
        return genai.GenerativeModel(model_name=selecionado, system_instruction=prompt_base)
    except: return None

model = inicializar_ia(CHAVE_API)

# --- FUNÇÕES DE APOIO ---
def tr(texto):
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def extrair_texto_flexivel(texto):
    dados = {"fornecedor": "", "edital": "", "objeto": "", "checklist": []}
    linhas = texto.split('\n')
    for linha in linhas:
        l = linha.strip()
        if not l: continue
        if "FORNECEDOR:" in l.upper(): dados["fornecedor"] = l.split(":", 1)[1].strip()
        elif "EDITAL:" in l.upper() or "ARP:" in l.upper() or "EMPENHO:" in l.upper(): dados["edital"] = l.split(":", 1)[1].strip()
        elif "OBJETO:" in l.upper(): dados["objeto"] = l.split(":", 1)[1].strip()
        elif l.startswith(("-", "*", "•")) or (l[0].isdigit() and "." in l[:3]):
            item = re.sub(r'^[-*•0-9.\s]+', '', l)
            if len(item) > 3: dados["checklist"].append({"id": time.time() + len(dados["checklist"]), "texto": item})
    return dados

# --- INTERFACE ---
st.set_page_config(page_title="Checklist Pro", layout="centered")

if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "dados_auto" not in st.session_state: st.session_state.dados_auto = {}
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "erro_ia" not in st.session_state: st.session_state.erro_ia = False

st.markdown('<h2 style="color: #009A44; text-align: center;">📋 RECEBIMENTO TÉCNICO</h2>', unsafe_allow_html=True)

# --- CARGA DE DADOS ---
if not st.session_state.checklist_items:
    natureza = st.radio("Tipo:", ["Consumo (Definitivo)", "Permanente (Provisório)"], horizontal=True)
    pdf_file = st.file_uploader("Upload do PDF", type="pdf")
    
    col1, col2 = st.columns(2)
    
    if col1.button("🔍 ANALISAR COM IA"):
        if pdf_file:
            with st.spinner("IA processando..."):
                try:
                    prompt = f"Analise para recebimento {natureza}. Extraia FORNECEDOR, EDITAL, OBJETO e CHECKLIST técnico. Use '-' para itens."
                    res = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_file.read()}, prompt])
                    dados = extrair_texto_flexivel(res.text)
                    st.session_state.dados_auto = dados
                    st.session_state.checklist_items = dados["checklist"]
                    st.session_state.natureza_escolhida = natureza
                    st.rerun()
                except Exception as e:
                    st.session_state.erro_ia = True
                    st.error("⚠️ Cota da IA Esgotada.")
    
    if col2.button("📝 ENTRADA MANUAL") or st.session_state.erro_ia:
        st.info("💡 **Cota esgotada?** Peça ao Gemini ou Copilot para extrair os dados e cole abaixo:")
        texto_manual = st.text_area("Cole aqui o texto da IA (Fornecedor, Edital, Itens...):")
        if st.button("🚀 Carregar Texto"):
            dados = extrair_texto_flexivel(texto_manual)
            st.session_state.dados_auto = dados
            st.session_state.checklist_items = dados["checklist"]
            st.session_state.natureza_escolhida = natureza
            st.rerun()

# --- FORMULÁRIO E CHECKLIST ---
if st.session_state.checklist_items:
    obj_curto = " ".join(st.session_state.dados_auto.get("objeto", "BEM").split()[:5]).upper()
    st.success(f"CONFERINDO: {obj_curto}")

    with st.container(border=True):
        c1, c2 = st.columns(2)
        edital = c1.text_input("Edital/ARP:", value=st.session_state.dados_auto.get("edital", ""))
        fornec = c2.text_input("Fornecedor:", value=st.session_state.dados_auto.get("fornecedor", ""))
        nf = c1.text_input("Nota Fiscal:")
        qtd = c2.text_input("Quantidade:")
        servidor = st.text_input("Nome do Servidor (Atestante):")

    st.write("### 1. Itens Técnicos")
    todos_ok = True
    for i, it in enumerate(st.session_state.checklist_items):
        uid = it["id"]
        with st.container(border=True):
            col_a, col_b, col_c = st.columns([0.1, 0.7, 0.2])
            st.session_state.conferidos[uid] = col_a.checkbox("", key=f"c_{uid}")
            if not st.session_state.conferidos[uid]: todos_ok = False
            it["texto"] = col_b.text_input("", value=it["texto"], key=f"t_{uid}", label_visibility="collapsed")
            if col_c.button("🗑️", key=f"d_{uid}"):
                st.session_state.checklist_items.pop(i); st.rerun()
            
            foto = st.camera_input(f"Foto Item {i+1}", key=f"f_{uid}")
            if foto: st.session_state.fotos[uid] = foto

    obs_geral = st.text_area("Observações/Pendências:") if not todos_ok else ""

    if st.button("🚀 GERAR PDF FINAL"):
        if not servidor: st.error("Informe o servidor.")
        else:
            try:
                pdf = FPDF(); pdf.set_margins(15, 15, 15); pdf.add_page()
                pdf.set_font("Arial", 'B', 16); pdf.set_text_color(0, 154, 68)
                pdf.cell(180, 10, tr("RELATÓRIO DE CONFORMIDADE TÉCNICA"), ln=True, align='C')
                pdf.ln(5)
                # Cabeçalho
                pdf.set_fill_color(240, 240, 240); pdf.set_text_color(0); pdf.set_font("Arial", 'B', 10)
                pdf.cell(40, 8, " FORNECEDOR:", border=1, fill=True); pdf.set_font("Arial", '', 10); pdf.cell(140, 8, tr(fornec.upper()), border=1, ln=True)
                pdf.set_font("Arial", 'B', 10); pdf.cell(40, 8, " EDITAL/NF:", border=1, fill=True); pdf.set_font("Arial", '', 10); pdf.cell(140, 8, tr(f"{edital} / NF: {nf}"), border=1, ln=True)
                pdf.ln(5)
                # Itens
                for it in st.session_state.checklist_items:
                    u = it["id"]
                    status = "[OK]" if st.session_state.conferidos.get(u) else "[PENDENTE]"
                    pdf.set_font("Arial", 'B', 10); pdf.multi_cell(180, 7, tr(f"{status} {it['texto']}"))
                    if u in st.session_state.fotos:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(st.session_state.fotos[u].getvalue())
                            pdf.image(tmp.name, x=40, w=130); pdf.ln(2)
                    pdf.ln(2)
                
                pdf.ln(10)
                atesto = "DEFINITIVO" if "Consumo" in st.session_state.natureza_escolhida else "PROVISÓRIO"
                msg = f"ATESTO O RECEBIMENTO {atesto} POR CONFORMIDADE." if todos_ok else f"PENDENCIAS: {obs_geral}"
                pdf.set_fill_color(245, 245, 245); pdf.multi_cell(180, 10, tr(msg), border=1, align='C', fill=True)
                pdf.ln(20); pdf.cell(180, 8, "________________________________________", ln=True, align='C')
                pdf.cell(180, 8, tr(f"SERVIDOR: {servidor.upper()}"), ln=True, align='C')
                
                out = pdf.output(dest='S')
                if isinstance(out, str): out = out.encode('latin-1')
                st.download_button("📥 Baixar PDF", data=out, file_name="Relatorio.pdf", mime="application/pdf")
            except Exception as e: st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Nova Inspeção"): st.session_state.clear(); st.rerun()
