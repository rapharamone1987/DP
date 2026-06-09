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
        
        prompt_base = (
            "Você é um Especialista em Recebimento de bens e materiais no setor público. "
            "Se o recebimento for Definitivo, Liste os detalhes técnicos reais descritos no PDF. "
            "Se for Provisório, a conferencia é simplificada (MARCA/MODELO, COR, QUANTIDADE). "
            "NÃO use a palavra 'conforme'. Extraia o dado real (Ex: 'Marca: Midea')."
        )
        return genai.GenerativeModel(model_name=selecionado, system_instruction=prompt_base)
    except: return None

model = inicializar_ia(CHAVE_API)

# --- 2. FUNÇÕES DE SUPORTE (TEXTO E PDF) ---
def tr(texto):
    """Trata acentuação para PDF Latin-1"""
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def extrair_texto_flexivel(texto):
    """Converte resposta da IA ou texto colado em dados estruturados"""
    dados = {"fornecedor": "", "edital": "", "objeto": "", "checklist": []}
    linhas = texto.split('\n')
    for linha in linhas:
        l = linha.strip()
        if not l or len(l) < 3: continue
        if "FORNECEDOR:" in l.upper(): dados["fornecedor"] = l.split(":", 1)[1].strip()
        elif "EDITAL:" in l.upper() or "ARP:" in l.upper() or "EMPENHO:" in l.upper(): dados["edital"] = l.split(":", 1)[1].strip()
        elif "OBJETO:" in l.upper(): dados["objeto"] = l.split(":", 1)[1].strip()
        elif l.startswith(("-", "*", "•")) or (l[0].isdigit() and "." in l[:3]):
            item = re.sub(r'^[-*•0-9.\s]+', '', l)
            if len(item) > 3 and "CHECKLIST" not in item.upper():
                dados["checklist"].append({"id": time.time() + len(dados["checklist"]), "texto": item})
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

# --- 3. INTERFACE E ESTILO ---
st.set_page_config(page_title="Checklist Pro", layout="centered")
st.markdown("""<style>
    .titulo-v { color: #009A44; font-weight: bold; font-size: 24px; text-align: center; text-transform: uppercase; }
    .caixa-info { background-color: #F8F9FA; padding: 15px; border-radius: 8px; border: 1px solid #DEE2E6; margin-bottom: 20px; }
    .barra { background-color: #009A44; color: white; padding: 10px; border-radius: 5px; font-weight: bold; }
</style>""", unsafe_allow_html=True)

if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "dados_auto" not in st.session_state: st.session_state.dados_auto = {"fornecedor":"","edital":"","objeto":""}
if "item_da_foto" not in st.session_state: st.session_state.item_da_foto = None

st.markdown('<p class="titulo-v">📋 Recebimento Técnico Inteligente</p>', unsafe_allow_html=True)

# --- 4. CARGA DE DADOS (COM MODO DE EMERGÊNCIA) ---
if not st.session_state.checklist_items:
    modo = st.radio("Escolha o método:", ["Analisar PDF (IA)", "Colar Texto (Cota Esgotada)"], horizontal=True)
    
    if modo == "Analisar PDF (IA)":
        natureza = st.radio("Tipo:", ["Consumo (Definitivo)", "Permanente (Provisório)"], horizontal=True)
        pdf_file = st.file_uploader("Upload do PDF", type="pdf")
        if pdf_file and st.button("🔍 ANALISAR AGORA"):
            with st.spinner("IA Processando..."):
                try:
                    prompt = f"Analise o PDF para {natureza}. EXTRAIA MARCA, MODELO e DADOS REAIS. Formato: FORNECEDOR: x, EDITAL: x, OBJETO: x, CHECKLIST: - item"
                    res = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_file.read()}, prompt])
                    dados = extrair_texto_flexivel(res.text)
                    st.session_state.dados_auto = dados
                    st.session_state.checklist_items = dados["checklist"]
                    st.session_state.natureza_final = natureza
                    st.rerun()
                except Exception as e:
                    st.error("⚠️ Cota atingida ou erro na IA. Use o modo 'Colar Texto'.")
    
    else:
        st.info("💡 Vá no Gemini/Copilot, anexe o PDF e cole o resultado abaixo:")
        natureza = st.radio("Tipo:", ["Consumo (Definitivo)", "Permanente (Provisório)"], horizontal=True)
        texto_manual = st.text_area("Cole o texto aqui:")
        if st.button("🚀 Carregar Dados"):
            dados = extrair_texto_flexivel(texto_manual)
            st.session_state.dados_auto = dados
            st.session_state.checklist_items = dados["checklist"]
            st.session_state.natureza_final = natureza
            st.rerun()

# --- 5. EXECUÇÃO DO CHECKLIST ---
if st.session_state.checklist_items:
    obj_nome = st.session_state.dados_auto.get("objeto", "RECEBIMENTO")
    obj_curto = " ".join(obj_nome.split()[:6]).upper()
    st.markdown(f'<div class="barra">CHECKLIST: {obj_curto}</div>', unsafe_allow_html=True)

    with st.container(border=True):
        c1, c2 = st.columns(2)
        fornec_val = c1.text_input("Fornecedor:", value=st.session_state.dados_auto["fornecedor"])
        edital_val = c2.text_input("Edital/ARP/Empenho:", value=st.session_state.dados_auto["edital"])
        nf_val = c1.text_input("Nº Nota Fiscal:")
        qtd_val = c2.text_input("Quantidade:")
        placa_val = c1.text_input("Placa / ID / Patrimônio:")
        centro_val = c2.text_input("Centro de Custo:") if "Permanente" in st.session_state.natureza_final else ""

    st.write("---")
    todos_ok = True
    for i, it in enumerate(st.session_state.checklist_items):
        uid = it["id"]
        with st.container(border=True):
            col_ch, col_tx, col_ex = st.columns([0.1, 0.75, 0.15])
            st.session_state.conferidos[uid] = col_ch.checkbox("OK", key=f"c_{uid}", value=st.session_state.conferidos.get(uid, False))
            if not st.session_state.conferidos[uid]: todos_ok = False
            
            it["texto"] = col_tx.text_input("", value=it["texto"], key=f"t_{uid}", label_visibility="collapsed")
            if col_ex.button("🗑️", key=f"d_{uid}"):
                st.session_state.checklist_items.pop(i); st.rerun()

            if st.session_state.item_da_foto == uid:
                f = st.camera_input(f"Foto Item {i+1}", key=f"cam_{uid}")
                if f: st.session_state.fotos[uid] = f
                if st.button("✅ Salvar Foto", key=f"s_{uid}"): st.session_state.item_da_foto = None; st.rerun()
            else:
                cb, cp = st.columns([0.4, 0.6])
                if cb.button("📸 Foto", key=f"bc_{uid}"): st.session_state.item_da_foto = uid; st.rerun()
                if uid in st.session_state.fotos: cp.image(st.session_state.fotos[uid], width=120)

    if st.button("➕ Adicionar Requisito Manual"):
        st.session_state.checklist_items.append({"id": time.time(), "texto": "Novo Item"})
        st.rerun()

    obs_geral = st.text_area("Observações / Pendências:") if not todos_ok else ""
    servidor = st.text_input("Nome do Servidor (Atestante):")

    # --- 6. GERAÇÃO DO PDF ---
    if st.button("🚀 GERAR RELATÓRIO FINAL"):
        if not servidor: st.error("Informe o nome do servidor.")
        else:
            try:
                pdf = FPDF(); pdf.set_margins(15, 15, 15); pdf.add_page()
                pdf.set_font("Arial", 'B', 16); pdf.set_text_color(0, 154, 68)
                pdf.cell(180, 10, tr("RELATÓRIO DE CONFORMIDADE TÉCNICA"), ln=True, align='C')
                pdf.set_font("Arial", 'B', 12); pdf.multi_cell(180, 8, tr(obj_curto), align='C')
                pdf.ln(5)

                # Cabeçalho
                pdf.set_fill_color(240, 240, 240); pdf.set_text_color(50); pdf.set_font("Arial", 'B', 9)
                def row(l, v):
                    pdf.set_font("Arial", 'B', 9); pdf.cell(40, 8, tr(f" {l}"), border=1, fill=True)
                    pdf.set_font("Arial", '', 9); pdf.cell(140, 8, tr(f" {v}"), border=1, ln=True)
                row("FORNECEDOR:", fornec_val.upper()); row("EDITAL/ARP:", edital_val)
                row("NOTA FISCAL:", nf_val); row("QUANTIDADE:", qtd_val)
                row("IDENTIFICAÇÃO:", placa_val.upper())
                if centro_val: row("CENTRO CUSTO:", centro_val.upper())
                pdf.ln(8)

                pdf.set_fill_color(0, 154, 68); pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 11)
                pdf.cell(180, 10, tr(" 1. ITENS DE CONFERÊNCIA TÉCNICA"), ln=True, fill=True)
                pdf.set_text_color(0, 0, 0); pdf.ln(4)

                for it in st.session_state.checklist_items:
                    u = it["id"]
                    if pdf.get_y() > 250: pdf.add_page()
                    desenhar_check(pdf, 17, pdf.get_y()+1, st.session_state.conferidos.get(u))
                    pdf.set_x(25); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(165, 7, tr(it["texto"]))
                    
                    if u in st.session_state.fotos:
                        pdf.ln(2)
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(st.session_state.fotos[u].getvalue()); tmp_path = tmp.name
                            with Image.open(tmp_path) as img:
                                w, h = img.size; aspect = h/w; print_h = 140 * aspect
                        if pdf.get_y() + print_h > 270: pdf.add_page()
                        y_start = pdf.get_y()
                        pdf.image(tmp_path, x=35, y=y_start, w=140)
                        pdf.set_y(y_start + print_h + 5); os.unlink(tmp_path)
                    pdf.ln(2)

                # Atesto
                if pdf.get_y() > 230: pdf.add_page()
                pdf.ln(10)
                if todos_ok:
                    pdf.set_fill_color(235, 245, 235); pdf.set_draw_color(0, 154, 68); pdf.set_font("Arial", 'B', 11)
                    t = "RECEBIMENTO DEFINITIVO" if "Consumo" in st.session_state.natureza_final else "RECEBIMENTO PROVISÓRIO"
                    pdf.multi_cell(180, 12, tr(f"ATESTO O {t} DO OBJETO POR ESTAR EM PLENA CONFORMIDADE."), border=1, align='C', fill=True)
                else:
                    pdf.set_fill_color(255, 240, 240); pdf.set_draw_color(200, 0, 0); pdf.set_font("Arial", 'B', 10)
                    pdf.multi_cell(180, 8, tr(f"PENDÊNCIAS REGISTRADAS:\n{obs_geral}"), border=1, fill=True)

                pdf.ln(25); pdf.line(60, pdf.get_y(), 150, pdf.get_y())
                pdf.cell(180, 8, tr(f"SERVIDOR: {servidor.upper()}"), ln=True, align='C')
                
                out = pdf.output(dest='S')
                if isinstance(out, str): out = out.encode('latin-1')
                st.download_button("📥 Baixar Relatório", data=out, file_name=f"Checklist_{nf_val}.pdf", mime="application/pdf")
            except Exception as e: st.error(f"Erro: {e}")

if st.sidebar.button("Nova Inspeção"): st.session_state.clear(); st.rerun()
