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
        
        prompt_base = (
            "Você é um Especialista em Recebimento de bens e materiais no setor público. "
            "Extraia detalhes técnicos reais descritos no PDF. NÃO use a palavra 'conforme'. "
            "Extraia o dado real (Ex: 'Marca: Midea')."
        )
        return genai.GenerativeModel(model_name=selecionado, system_instruction=prompt_base)
    except: return None

model = inicializar_ia(CHAVE_API)

# --- 2. FUNÇÕES DE SUPORTE ---
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
            if len(item) > 5 and "CHECKLIST" not in item.upper():
                # Criamos um dicionário com ID único para cada item
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

# --- 3. INTERFACE ---
st.set_page_config(page_title="Checklist IA", layout="centered")
st.markdown("""<style>
    .titulo-verde { color: #009A44; font-weight: bold; font-size: 22px; text-transform: uppercase; text-align: center; }
    .caixa { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #ddd; }
    .barra { background-color: #009A44; color: white; padding: 8px; font-weight: bold; border-radius: 5px; }
</style>""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADOS ---
if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "dados_auto" not in st.session_state: st.session_state.dados_auto = {"fornecedor":"","edital":"","objeto":""}
if "item_da_foto" not in st.session_state: st.session_state.item_da_foto = None

st.markdown('<p class="titulo-verde">📋 Recebimento Técnico</p>', unsafe_allow_html=True)
natureza = st.radio("Tipo:", ["Consumo (Definitivo)", "Permanente (Provisório)"], horizontal=True)

# --- 4. EXTRAÇÃO ---
pdf_file = st.file_uploader("Upload do PDF", type="pdf")

if pdf_file and not st.session_state.checklist_items:
    if st.button("🔍 ANALISAR DOCUMENTO"):
        with st.spinner("IA extraindo dados..."):
            try:
                prompt = f"Analise o PDF para recebimento {natureza}. EXTRAIA MARCA, MODELO e ITENS REAIS. Formato: FORNECEDOR: x, EDITAL: x, OBJETO: x, CHECKLIST: - item"
                res = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_file.read()}, prompt])
                dados = extrair_texto_flexivel(res.text)
                st.session_state.dados_auto = dados
                st.session_state.checklist_items = dados["checklist"]
                st.rerun()
            except Exception as e: st.error(f"Erro: {e}")

# --- 5. CHECKLIST DINÂMICO ---
if st.session_state.checklist_items:
    obj_curto = " ".join(st.session_state.dados_auto.get("objeto", "BEM").split()[:5]).upper()
    st.markdown(f'<p class="titulo-verde">CONFERÊNCIA: {obj_curto}</p>', unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="caixa">', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        edital_val = c1.text_input("Edital/ARP:", value=st.session_state.dados_auto["edital"])
        fornec_val = c2.text_input("Fornecedor:", value=st.session_state.dados_auto["fornecedor"])
        placa = c1.text_input("Placa / ID / Série:")
        centro_custo = c2.text_input("Centro de Custo:") if "Permanente" in natureza else ""
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="barra">1. ESPECIFICAÇÕES TÉCNICAS</div>', unsafe_allow_html=True)
    
    todos_ok = True
    # Usamos uma cópia da lista para iterar com segurança durante a exclusão
    for i, item_obj in enumerate(st.session_state.checklist_items):
        uid = item_obj["id"]
        
        with st.container(border=True):
            col_ch, col_edit, col_exc = st.columns([0.1, 0.75, 0.15])
            
            # Checkbox
            st.session_state.conferidos[uid] = col_ch.checkbox("", key=f"c_{uid}", value=st.session_state.conferidos.get(uid, False))
            if not st.session_state.conferidos[uid]: todos_ok = False
            
            # Texto Editável (Atualiza o objeto na lista)
            item_obj["texto"] = col_edit.text_input(f"Item {uid}", value=item_obj["texto"], key=f"txt_{uid}", label_visibility="collapsed")
            
            # Botão Excluir Corrigido
            if col_exc.button("🗑️", key=f"del_{uid}"):
                st.session_state.checklist_items.pop(i)
                # Remove lixo do estado
                if uid in st.session_state.conferidos: del st.session_state.conferidos[uid]
                if uid in st.session_state.fotos: del st.session_state.fotos[uid]
                st.rerun()

            # Câmera por item
            if st.session_state.item_da_foto == uid:
                foto = st.camera_input(f"Capturar Foto", key=f"cam_{uid}")
                if foto:
                    st.session_state.fotos[uid] = foto
                    if st.button(f"✅ Salvar Foto", key=f"save_{uid}"):
                        st.session_state.item_da_foto = None; st.rerun()
            else:
                c_btn, c_prev = st.columns([0.4, 0.6])
                if c_btn.button("📸 Foto", key=f"btn_cam_{uid}"):
                    st.session_state.item_da_foto = uid; st.rerun()
                if uid in st.session_state.fotos: c_prev.image(st.session_state.fotos[uid], width=80)

    if st.button("➕ Adicionar Requisito Manual"):
        st.session_state.checklist_items.append({"id": time.time(), "texto": "Novo Item"})
        st.rerun()

    obs_geral = st.text_area("⚠️ Observações:") if not todos_ok else ""
    servidor = st.text_input("Servidor Responsável:")

    # --- 6. PDF ---
    if st.button("🚀 GERAR PDF FINAL"):
        if not servidor: st.error("Informe o servidor.")
        else:
            try:
                pdf = FPDF(); pdf.set_margins(20, 20, 20); pdf.add_page()
                pdf.set_font("Arial", 'B', 14); pdf.set_text_color(0, 154, 68)
                pdf.multi_cell(170, 10, f"RELATORIO - {obj_curto}", align='C')
                pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.set_text_color(0, 0, 0)
                pdf.cell(170, 8, f"EDITAL: {edital_val}", ln=True, border='B')
                pdf.write(8, "FORNECEDOR: "); pdf.multi_cell(140, 8, fornec_val.upper())
                pdf.set_font("Arial", 'B', 10); pdf.cell(170, 8, f"ID: {placa.upper()}", ln=True)
                if centro_custo: pdf.write(8, "C. CUSTO: "); pdf.multi_cell(140, 8, centro_custo.upper())
                
                pdf.ln(5); pdf.set_fill_color(0, 154, 68); pdf.set_text_color(255, 255, 255)
                pdf.cell(170, 10, " 1. CONFERENCIA REALIZADA", ln=True, fill=True)
                pdf.set_text_color(0, 0, 0); pdf.ln(3)

                for it in st.session_state.checklist_items:
                    u = it["id"]
                    desenhar_check(pdf, 22, pdf.get_y()+1, st.session_state.conferidos.get(u))
                    pdf.set_x(28); pdf.set_font("Arial", 'B', 10)
                    pdf.multi_cell(160, 7, it["texto"].encode('latin-1','replace').decode('latin-1'))
                    if u in st.session_state.fotos:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(st.session_state.fotos[u].getvalue()); tmp_path = tmp.name
                        if pdf.get_y() > 180: pdf.add_page()
                        pdf.image(tmp_path, x=35, w=130); pdf.ln(5); os.unlink(tmp_path)
                    pdf.ln(2)

                pdf.ln(10)
                if todos_ok:
                    pdf.set_fill_color(245, 245, 245); pdf.set_font("Arial", 'B', 10)
                    t = "RECEBIMENTO DEFINITIVO" if "Consumo" in natureza else "RECEBIMENTO PROVISORIO"
                    pdf.multi_cell(170, 10, f"ATESTO O {t} DO OBJETO POR ESTAR EM CONFORMIDADE.", border=1, align='C', fill=True)
                else:
                    pdf.set_font("Arial", 'B', 10); pdf.set_text_color(200, 0, 0)
                    pdf.multi_cell(170, 8, f"PENDENCIAS: {obs_geral}", border=1)

                pdf.ln(20); pdf.set_text_color(0, 0, 0)
                pdf.cell(170, 8, "________________________________________", ln=True, align='C')
                pdf.cell(170, 6, f"SERVIDOR: {servidor.upper()}", ln=True, align='C')
                st.download_button("📥 Baixar PDF", data=pdf.output(dest='S').encode('latin-1','replace'), file_name="Checklist.pdf")
            except Exception as e: st.error(f"Erro: {e}")

if st.sidebar.button("Nova Inspeção"):
    st.session_state.clear(); st.rerun()
