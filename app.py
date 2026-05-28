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
        prompt_base = "Você é um Especialista em Recebimento de bens públicos. Extraia dados técnicos reais descritos no PDF. NÃO use 'conforme'. Extraia marca, modelo e especificações."
        return genai.GenerativeModel(model_name=selecionado, system_instruction=prompt_base)
    except: return None

model = inicializar_ia(CHAVE_API)

# --- 2. CLASSE PDF CUSTOMIZADA (LAYOUT RICO) ---
class RelatorioPDF(FPDF):
    def header(self):
        # Linha verde no topo
        self.set_fill_color(0, 154, 68)
        self.rect(0, 0, 210, 10, 'F')
        self.ln(12)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", 'I', 8)
        self.set_text_color(128)
        data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.cell(0, 10, f"Gerado em {data_hora} - Página {self.page_no()}/{{nb}}", 0, 0, 'C')

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

# --- 3. SUPORTE TEXTO ---
def extrair_texto_flexivel(texto):
    dados = {"fornecedor": "", "edital": "", "objeto": "", "checklist": []}
    linhas = texto.split('\n')
    for linha in linhas:
        l = linha.strip()
        if not l or len(l) < 3: continue
        if "FORNECEDOR:" in l.upper(): dados["fornecedor"] = l.split(":", 1)[1].strip()
        elif "EDITAL:" in l.upper() or "ARP:" in l.upper(): dados["edital"] = l.split(":", 1)[1].strip()
        elif "OBJETO:" in l.upper(): dados["objeto"] = l.split(":", 1)[1].strip()
        elif l.startswith(("-", "*", "•")) or (len(l) > 3 and l[0].isdigit() and "." in l[:3]):
            item = re.sub(r'^[-*•0-9.\s]+', '', l)
            if len(item) > 5:
                dados["checklist"].append({"id": time.time() + len(dados["checklist"]), "texto": item})
    return dados

# --- 4. INTERFACE STREAMLIT ---
st.set_page_config(page_title="Checklist Pro", layout="centered")
st.markdown("<style>.titulo-v { color: #009A44; font-weight: bold; font-size: 24px; text-align: center; } .barra { background-color: #009A44; color: white; padding: 10px; border-radius: 5px; font-weight: bold; }</style>", unsafe_allow_html=True)

if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "dados_auto" not in st.session_state: st.session_state.dados_auto = {"fornecedor":"","edital":"","objeto":""}
if "item_da_foto" not in st.session_state: st.session_state.item_da_foto = None

st.markdown('<p class="titulo-v">📋 Recebimento Técnico Inteligente</p>', unsafe_allow_html=True)
natureza = st.radio("Tipo:", ["Consumo (Definitivo)", "Permanente (Provisório)"], horizontal=True)

pdf_file = st.file_uploader("Upload do PDF", type="pdf")

if pdf_file and not st.session_state.checklist_items:
    if st.button("🔍 ANALISAR DOCUMENTO"):
        with st.spinner("Extraindo dados..."):
            try:
                prompt = f"Analise o PDF para {natureza}. EXTRAIA MARCA, MODELO e ESPECIFICACOES REAIS. Formato: FORNECEDOR: x, EDITAL: x, OBJETO: x, CHECKLIST: - item"
                res = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_file.read()}, prompt])
                dados = extrair_texto_flexivel(res.text)
                st.session_state.dados_auto = dados
                st.session_state.checklist_items = dados["checklist"]
                st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

# --- 5. CHECKLIST ---
if st.session_state.checklist_items:
    obj_curto = " ".join(st.session_state.dados_auto.get("objeto", "BEM").split()[:5]).upper()
    st.markdown(f'<div class="barra">{obj_curto}</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    edital_val = c1.text_input("Edital/ARP:", value=st.session_state.dados_auto["edital"])
    fornec_val = c2.text_input("Fornecedor:", value=st.session_state.dados_auto["fornecedor"])
    placa = c1.text_input("Placa / ID / Série:")
    centro_custo = c2.text_input("Centro de Custo:") if "Permanente" in natureza else ""

    st.write("---")
    todos_ok = True
    for i, it in enumerate(st.session_state.checklist_items):
        uid = it["id"]
        with st.container(border=True):
            col_ch, col_tx, col_ex = st.columns([0.1, 0.75, 0.15])
            st.session_state.conferidos[uid] = col_ch.checkbox("", key=f"c_{uid}", value=st.session_state.conferidos.get(uid, False))
            if not st.session_state.conferidos[uid]: todos_ok = False
            it["texto"] = col_tx.text_input("", value=it["texto"], key=f"t_{uid}", label_visibility="collapsed")
            if col_ex.button("🗑️", key=f"d_{uid}"):
                st.session_state.checklist_items.pop(i); st.rerun()

            if st.session_state.item_da_foto == uid:
                f = st.camera_input(f"Foto", key=f"cam_{uid}")
                if f: st.session_state.fotos[uid] = f
                if st.button("✅ Salvar", key=f"s_{uid}"): st.session_state.item_da_foto = None; st.rerun()
            else:
                cb, cp = st.columns([0.4, 0.6])
                if cb.button("📸 Foto", key=f"bc_{uid}"): st.session_state.item_da_foto = uid; st.rerun()
                if uid in st.session_state.fotos: cp.image(st.session_state.fotos[uid], width=100)

    if st.button("➕ Adicionar Requisito"):
        st.session_state.checklist_items.append({"id": time.time(), "texto": "Novo Item"})
        st.rerun()

    obs_geral = st.text_area("Observações:") if not todos_ok else ""
    servidor = st.text_input("Servidor Responsável:")

    # --- 6. GERAÇÃO DO PDF (LAYOUT MELHORADO) ---
    if st.button("🚀 GERAR RELATÓRIO FINAL"):
        if not servidor: st.error("Informe o servidor.")
        else:
            try:
                pdf = RelatorioPDF(); pdf.alias_nb_pages(); pdf.set_margins(15, 15, 15); pdf.add_page()
                
                # Título
                pdf.set_font("Arial", 'B', 16); pdf.set_text_color(0, 154, 68)
                pdf.cell(180, 10, f"RELATORIO DE CONFORMIDADE TECNICA", ln=True, align='C')
                pdf.set_font("Arial", 'B', 12); pdf.cell(180, 8, obj_curto, ln=True, align='C')
                pdf.ln(5)

                # Tabela de Dados (Cabeçalho Cinza)
                pdf.set_fill_color(240, 240, 240); pdf.set_font("Arial", 'B', 9); pdf.set_text_color(50)
                pdf.cell(40, 8, " EDITAL/ARP:", border=1, fill=True)
                pdf.set_font("Arial", '', 9); pdf.cell(140, 8, f" {edital_val}", border=1, ln=True)
                
                pdf.set_font("Arial", 'B', 9)
                pdf.cell(40, 8, " FORNECEDOR:", border=1, fill=True)
                pdf.set_font("Arial", '', 9); pdf.cell(140, 8, f" {fornec_val.upper()}", border=1, ln=True)
                
                pdf.set_font("Arial", 'B', 9)
                pdf.cell(40, 8, " IDENTIFICACAO:", border=1, fill=True)
                pdf.set_font("Arial", '', 9); pdf.cell(140, 8, f" {placa.upper()}", border=1, ln=True)
                
                if centro_custo:
                    pdf.set_font("Arial", 'B', 9)
                    pdf.cell(40, 8, " CENTRO CUSTO:", border=1, fill=True)
                    pdf.set_font("Arial", '', 9); pdf.cell(140, 8, f" {centro_custo.upper()}", border=1, ln=True)
                pdf.ln(8)

                # Barra de Seção
                pdf.set_fill_color(0, 154, 68); pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 11)
                pdf.cell(180, 10, " 1. ITENS DE CONFERENCIA TECNICA", ln=True, fill=True)
                pdf.set_text_color(0, 0, 0); pdf.ln(4)

                # Loop de Itens
                for it in st.session_state.checklist_items:
                    u = it["id"]
                    y_at = pdf.get_y()
                    desenhar_check(pdf, 17, y_at+1, st.session_state.conferidos.get(u))
                    pdf.set_x(25); pdf.set_font("Arial", 'B', 10)
                    pdf.multi_cell(165, 7, it["texto"].encode('latin-1','replace').decode('latin-1'))
                    
                    if u in st.session_state.fotos:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(st.session_state.fotos[u].getvalue()); tmp_path = tmp.name
                        if pdf.get_y() > 200: pdf.add_page()
                        # Foto com moldura
                        pdf.set_draw_color(200); pdf.rect(30, pdf.get_y()+2, 140, 85)
                        pdf.image(tmp_path, x=31, y=pdf.get_y()+3, w=138); pdf.ln(92)
                        os.unlink(tmp_path)
                    pdf.ln(2)

                # Caixa de Atesto / Pendência
                pdf.ln(10)
                if todos_ok:
                    pdf.set_fill_color(230, 245, 230); pdf.set_draw_color(0, 154, 68); pdf.set_font("Arial", 'B', 11)
                    txt = "RECEBIMENTO DEFINITIVO" if "Consumo" in natureza else "RECEBIMENTO PROVISORIO"
                    pdf.multi_cell(180, 12, f"ATESTO O {txt} DO OBJETO POR ESTAR EM PLENA CONFORMIDADE.", border=1, align='C', fill=True)
                else:
                    pdf.set_fill_color(255, 240, 240); pdf.set_draw_color(200, 0, 0); pdf.set_font("Arial", 'B', 10)
                    pdf.multi_cell(180, 8, f"PENDENCIAS REGISTRADAS:\n{obs_geral}", border=1, fill=True)

                # Assinatura
                pdf.ln(25); pdf.set_draw_color(0); pdf.set_text_color(0)
                pdf.line(60, pdf.get_y(), 150, pdf.get_y())
                pdf.cell(180, 8, f"SERVIDOR: {servidor.upper()}", ln=True, align='C')
                
                st.download_button("📥 Baixar Relatório", data=pdf.output(dest='S').encode('latin-1','replace'), file_name="Relatorio.pdf")
            except Exception as e: st.error(f"Erro: {e}")

if st.sidebar.button("Limpar Tudo"): st.session_state.clear(); st.rerun()
