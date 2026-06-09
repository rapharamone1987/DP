import streamlit as st
from groq import Groq
import pdfplumber
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import json
import time
import re
from PIL import Image

# --- 1. CONFIGURAÇÃO DO CLIENTE GROQ ---
if "GROQ_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GROQ_API_KEY"]
else:
    CHAVE_API = ""

client = None
if CHAVE_API:
    client = Groq(api_key=CHAVE_API)

# --- 2. FUNÇÕES DE APOIO ---
def extrair_texto_pdf(pdf_file):
    """Extrai texto do PDF para enviar ao Groq"""
    texto = ""
    with pdfplumber.open(pdf_file) as pdf:
        for pagina in pdf.pages:
            texto += pagina.extract_text() + "\n"
    return texto

def tr(texto):
    """Trata acentuação para PDF"""
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

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

def parse_resposta_ia(texto):
    """Extrai os campos do texto da IA"""
    dados = {"fornecedor": "", "edital": "", "objeto": "", "checklist": []}
    linhas = texto.split('\n')
    for linha in linhas:
        l = linha.strip()
        if "FORNECEDOR:" in l.upper(): dados["fornecedor"] = l.split(":", 1)[1].strip()
        elif "EDITAL:" in l.upper() or "ARP:" in l.upper(): dados["edital"] = l.split(":", 1)[1].strip()
        elif "OBJETO:" in l.upper(): dados["objeto"] = l.split(":", 1)[1].strip()
        elif l.startswith(("-", "*", "•")) or (len(l) > 3 and l[0].isdigit() and "." in l[:3]):
            item = re.sub(r'^[-*•0-9.\s]+', '', l)
            if len(item) > 5 and "CHECKLIST" not in item.upper():
                dados["checklist"].append({"id": time.time() + len(dados["checklist"]), "texto": item})
    return dados

# --- 3. INTERFACE STREAMLIT ---
st.set_page_config(page_title="Checklist Pro Groq", layout="centered")
st.markdown("""<style>
    .titulo-v { color: #009A44; font-weight: bold; font-size: 24px; text-align: center; text-transform: uppercase; }
    .caixa-info { background-color: #F8F9FA; padding: 15px; border-radius: 8px; border: 1px solid #DEE2E6; margin-bottom: 20px; }
    .barra { background-color: #009A44; color: white; padding: 10px; border-radius: 5px; font-weight: bold; }
</style>""", unsafe_allow_html=True)

if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "dados_auto" not in st.session_state: st.session_state.dados_auto = {}
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "item_da_foto" not in st.session_state: st.session_state.item_da_foto = None

st.markdown('<p class="titulo-v">📋 Recebimento Técnico (Groq Llama 3)</p>', unsafe_allow_html=True)

# --- 4. CARGA DE DADOS ---
if not st.session_state.checklist_items:
    natureza = st.radio("Tipo de Recebimento:", ["Consumo (Definitivo)", "Permanente (Provisório)"], horizontal=True)
    pdf_file = st.file_uploader("Upload do TR ou Empenho (PDF)", type="pdf")
    
    if pdf_file and client:
        if st.button("🔍 ANALISAR DOCUMENTO"):
            with st.spinner("IA Groq analisando texto do PDF..."):
                try:
                    # 1. Extrai texto do PDF
                    texto_pdf = extrair_texto_pdf(pdf_file)
                    
                    # 2. Envia para o Groq
                    prompt_sistema = (
                        "Você é um Especialista em Recebimento de bens públicos. "
                        f"O recebimento é {natureza}. Se Definitivo, liste detalhes técnicos reais. "
                        "Se Provisório, simplifique (Marca, Modelo, Cor, Qtd). NÃO use 'conforme'. "
                        "EXTRAIA OS DADOS DO TEXTO ABAIXO:"
                    )
                    
                    prompt_usuario = f"Texto do PDF:\n{texto_pdf}\n\nResponda no formato:\nFORNECEDOR: [nome]\nEDITAL: [numero]\nOBJETO: [nome curto]\nCHECKLIST:\n- [item real 1]\n- [item real 2]"

                    completion = client.chat.completions.create(
                        model="llama-3.1-70b-versatile",
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": prompt_usuario}
                        ],
                        temperature=0.1
                    )
                    
                    dados = parse_resposta_ia(completion.choices[0].message.content)
                    st.session_state.dados_auto = dados
                    st.session_state.checklist_items = dados["checklist"]
                    st.session_state.natureza_final = natureza
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro no Groq: {e}")
    elif not client:
        st.warning("⚠️ GROQ_API_KEY não configurada nos Secrets.")

# --- 5. CHECKLIST E CONFERÊNCIA ---
if st.session_state.checklist_items:
    obj_nome = st.session_state.dados_auto.get("objeto", "BEM")
    obj_curto = " ".join(obj_nome.split()[:5]).upper()
    st.markdown(f'<div class="barra">CHECKLIST: {obj_curto}</div>', unsafe_allow_html=True)

    with st.container(border=True):
        c1, c2 = st.columns(2)
        fornec_val = c1.text_input("Fornecedor:", value=st.session_state.dados_auto["fornecedor"])
        edital_val = c2.text_input("Edital/ARP/Empenho:", value=st.session_state.dados_auto["edital"])
        nf_val = c1.text_input("Nº Nota Fiscal:")
        qtd_val = c2.text_input("Quantidade:")
        servidor = st.text_input("Nome do Servidor (Atestante):")

    st.write("---")
    todos_ok = True
    for i, it in enumerate(st.session_state.checklist_items):
        uid = it["id"]
        with st.container(border=True):
            col_ch, col_tx, col_ex = st.columns([0.15, 0.7, 0.15])
            st.session_state.conferidos[uid] = col_ch.checkbox("OK", key=f"c_{uid}")
            if not st.session_state.conferidos[uid]: todos_ok = False
            it["texto"] = col_tx.text_input("", value=it["texto"], key=f"t_{uid}", label_visibility="collapsed")
            
            if col_ex.button("🗑️", key=f"d_{uid}"):
                st.session_state.checklist_items.pop(i); st.rerun()

            if st.session_state.item_da_foto == uid:
                f = st.camera_input(f"Capturar Foto", key=f"cam_{uid}")
                if f: st.session_state.fotos[uid] = f
                if st.button("✅ Salvar e Fechar", key=f"s_{uid}"):
                    st.session_state.item_da_foto = None; st.rerun()
            else:
                c_btn, c_prev = st.columns([0.4, 0.6])
                if c_btn.button("📸 Câmera", key=f"btn_{uid}"):
                    st.session_state.item_da_foto = uid; st.rerun()
                if uid in st.session_state.fotos: c_prev.image(st.session_state.fotos[uid], width=120)

    obs_geral = st.text_area("Observações / Pendências:") if not todos_ok else ""

    # --- 6. GERAÇÃO DO PDF ---
    if st.button("🚀 GERAR RELATÓRIO FINAL"):
        if not servidor: st.error("Informe o servidor.")
        else:
            try:
                pdf = FPDF(); pdf.set_margins(15, 15, 15); pdf.add_page()
                pdf.set_font("Arial", 'B', 16); pdf.set_text_color(0, 154, 68)
                pdf.cell(180, 10, tr("RELATÓRIO DE CONFORMIDADE TÉCNICA"), ln=True, align='C')
                pdf.set_font("Arial", 'B', 12); pdf.multi_cell(180, 8, tr(obj_curto), align='C')
                pdf.ln(5)

                # Cabeçalho PDF
                pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', 9); pdf.set_text_color(0)
                def row(l, v):
                    pdf.set_font("Arial", 'B', 9); pdf.cell(40, 8, tr(f" {l}"), border=1, fill=True)
                    pdf.set_font("Arial", '', 9); pdf.cell(140, 8, tr(f" {v}"), border=1, ln=True)
                row("FORNECEDOR:", fornec_val.upper()); row("EDITAL/ARP:", edital_val)
                row("NOTA FISCAL:", nf_val); row("QUANTIDADE:", qtd_val)
                pdf.ln(8)

                for it in st.session_state.checklist_items:
                    u = it["id"]
                    if pdf.get_y() > 250: pdf.add_page()
                    desenhar_check(pdf, 17, pdf.get_y()+1, st.session_state.conferidos.get(u))
                    pdf.set_x(25); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(165, 7, tr(it["texto"]))
                    
                    if u in st.session_state.fotos:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(st.session_state.fotos[u].getvalue()); tmp_path = tmp.name
                            with Image.open(tmp_path) as img:
                                w, h = img.size; aspect = h/w; print_h = 140 * aspect
                        if pdf.get_y() + print_h > 270: pdf.add_page()
                        pdf.image(tmp_path, x=35, y=pdf.get_y()+2, w=140)
                        pdf.set_y(pdf.get_y() + print_h + 5); os.unlink(tmp_path)
                
                pdf.ln(10)
                atesto = "DEFINITIVO" if "Consumo" in st.session_state.natureza_final else "PROVISÓRIO"
                msg = f"ATESTO O RECEBIMENTO {atesto} POR CONFORMIDADE." if todos_ok else f"PENDÊNCIAS: {obs_geral}"
                pdf.set_fill_color(245, 245, 245); pdf.multi_cell(180, 10, tr(msg), border=1, align='C', fill=todos_ok)
                pdf.ln(20); pdf.cell(180, 8, "________________________________________", ln=True, align='C')
                pdf.cell(180, 8, tr(f"SERVIDOR: {servidor.upper()}"), ln=True, align='C')
                
                out = pdf.output(dest='S')
                if isinstance(out, str): out = out.encode('latin-1')
                st.download_button("📥 Baixar PDF", data=out, file_name="Checklist.pdf", mime="application/pdf")
            except Exception as e: st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Nova Inspeção"): st.session_state.clear(); st.rerun()
