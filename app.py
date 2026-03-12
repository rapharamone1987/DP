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
        preferencia = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro']
        selecionado = next((p for p in preferencia if p in modelos), modelos[0])
        return genai.GenerativeModel(selecionado), selecionado
    except Exception as e:
        return None, str(e)

# --- 2. LAYOUT E ESTILO (CSS) ---
st.set_page_config(page_title="Checklist Técnico Profissional", layout="centered")

st.markdown("""
    <style>
    .titulo-verde { color: #009A44; font-weight: bold; font-size: 26px; text-transform: uppercase; margin-bottom: 2px; }
    .linha-verde { border-bottom: 4px solid #009A44; margin-bottom: 15px; }
    .sub-info { color: #555; font-size: 14px; font-weight: bold; margin-bottom: 10px; }
    .caixa-cinza { background-color: #F2F2F2; padding: 20px; border-radius: 10px; border: 1px solid #DDD; margin-bottom: 20px; }
    .barra-secao { background-color: #009A44; color: white; padding: 10px; font-weight: bold; border-radius: 5px; margin-top: 20px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. ESTADO DA SESSÃO ---
if "checklist_items" not in st.session_state: st.session_state.checklist_items = []
if "fotos" not in st.session_state: st.session_state.fotos = {}
if "conferidos" not in st.session_state: st.session_state.conferidos = {}
if "observacoes" not in st.session_state: st.session_state.observacoes = {}
if "dados_auto" not in st.session_state: 
    st.session_state.dados_auto = {"fornecedor": "", "edital": "", "processo": "", "objeto": "", "centro_custo": ""}

# --- 4. CONEXÃO ---
model, nome_modelo = carregar_modelo_seguro(CHAVE_API)

# --- 5. EXTRAÇÃO ---
st.markdown('<p class="titulo-verde">📋 Configuração do Checklist</p>', unsafe_allow_html=True)
pdf_file = st.file_uploader("Arraste o Termo de Referência aqui", type="pdf")

if pdf_file and not st.session_state.checklist_items:
    with st.spinner("IA processando documento..."):
        try:
            pdf_data = pdf_file.read()
            prompt = "Analise o TR e extraia em JSON: fornecedor, edital, processo, objeto, centro_custo e checklist (itens técnicos curtos)."
            response = model.generate_content([{'mime_type': 'application/pdf', 'data': pdf_data}, prompt])
            data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
            st.session_state.dados_auto = data
            st.session_state.checklist_items = data.get("checklist", [])
            # Inicializa checkboxes como False
            for i in range(len(st.session_state.checklist_items)):
                st.session_state.conferidos[i] = False
            st.rerun()
        except Exception as e:
            st.error(f"Erro na extração: {e}")

# --- 6. INTERFACE DE CABEÇALHO (ESTILO IMAGEM) ---
st.markdown(f'<p class="titulo-verde">CHECKLIST DE RECEBIMENTO TÉCNICO - {st.session_state.dados_auto["objeto"].upper() or "S/ OBJETO"}</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-info">EDITAL: {st.session_state.dados_auto["edital"]} | PROCESSO: {st.session_state.dados_auto["processo"]}</p>', unsafe_allow_html=True)
st.markdown('<div class="linha-verde"></div>', unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="caixa-cinza">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    servidor_atesta = c1.text_input("Servidor Responsável (Atestante):", placeholder="Nome completo / Matrícula")
    fornecedor = c2.text_input("Fornecedor:", value=st.session_state.dados_auto["fornecedor"])
    placa = c1.text_input("PLACA / Identificação do Bem:", placeholder="Ex: ABC-1234")
    centro_custo = c2.text_input("Centro de Custo:", value=st.session_state.dados_auto["centro_custo"])
    natureza = st.radio("Natureza do Bem:", ["Consumo", "Permanente"], horizontal=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --- 7. EXIBIÇÃO DO CHECKLIST ---
if st.session_state.checklist_items:
    st.markdown('<div class="barra-secao">1. MECÂNICA, FLUIDOS E ITENS TÉCNICOS</div>', unsafe_allow_html=True)
    
    todos_concluidos = True
    
    for i, item in enumerate(st.session_state.checklist_items):
        with st.container(border=True):
            col_check, col_texto = st.columns([0.1, 0.9])
            
            # Checkbox
            st.session_state.conferidos[i] = col_check.checkbox("OK", key=f"c_{i}")
            if not st.session_state.conferidos[i]:
                todos_concluidos = False # Se um falhar, não há atesto automático
            
            col_texto.write(f"**{item}**")
            
            # Foto Grande
            foto = st.camera_input(f"Capturar Imagem - Item {i+1}", key=f"f_{i}")
            if foto: st.session_state.fotos[i] = foto
            
            # Observação se pendente
            if not st.session_state.conferidos[i]:
                st.session_state.observacoes[i] = st.text_area(f"Observações/Pendências - Item {i+1}", key=f"obs_{i}")

    # --- 8. GERAÇÃO DO PDF ---
    st.divider()
    if st.button("📄 GERAR RELATÓRIO FINAL"):
        try:
            pdf = FPDF()
            pdf.add_page()
            
            # Cabeçalho PDF
            pdf.set_font("Arial", 'B', 16)
            pdf.set_text_color(0, 154, 68)
            pdf.multi_cell(190, 10, f"CHECKLIST DE RECEBIMENTO TECNICO - {st.session_state.dados_auto['objeto'].upper()}", align='C')
            pdf.set_font("Arial", 'B', 10)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(190, 7, f"EDITAL: {st.session_state.dados_auto['edital']} | PROCESSO: {st.session_state.dados_auto['processo']}", ln=True, align='C')
            pdf.ln(5)

            # Grid de Informações (Cinza)
            pdf.set_fill_color(242, 242, 242)
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(95, 10, f" SERVIDOR: {servidor_atesta.upper()}", border=1, fill=True)
            pdf.cell(95, 10, f" FORNECEDOR: {fornecedor.upper()}", border=1, ln=True, fill=True)
            pdf.cell(95, 10, f" PLACA: {placa.upper()}", border=1, fill=True)
            pdf.cell(95, 10, f" C. CUSTO: {centro_custo.upper()}", border=1, ln=True, fill=True)
            pdf.ln(10)

            # Título da Seção
            pdf.set_fill_color(0, 154, 68)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(190, 10, " 1. MECANICA E ITENS TECNICOS", ln=True, fill=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(5)

            # Listagem de Itens
            for idx, item_txt in enumerate(st.session_state.checklist_items):
                status = "[X] OK" if st.session_state.conferidos.get(idx) else "[ ] PENDENTE"
                pdf.set_font("Arial", 'B', 10)
                pdf.multi_cell(190, 8, f"{status} - {item_txt.encode('latin-1','ignore').decode('latin-1')}")
                
                # Observações se houver
                if not st.session_state.conferidos.get(idx):
                    pdf.set_font("Arial", 'I', 10)
                    pdf.set_text_color(200, 0, 0)
                    pdf.multi_cell(190, 7, f"   OBS: {st.session_state.observacoes.get(idx, 'Sem observações registradas.')}")
                    pdf.set_text_color(0, 0, 0)

                # Foto Grande
                if idx in st.session_state.fotos:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(st.session_state.fotos[idx].getvalue())
                        tmp_path = tmp.name
                    if pdf.get_y() > 200: pdf.add_page()
                    pdf.image(tmp_path, x=15, w=170) # Foto larga
                    pdf.ln(5)
                    os.unlink(tmp_path)
                pdf.ln(5)

            # --- LÓGICA FINAL DE ATESTO ---
            pdf.ln(10)
            if todos_concluidos:
                pdf.set_font("Arial", 'B', 11)
                pdf.set_fill_color(230, 230, 230)
                if natureza == "Permanente":
                    texto_atesto = f"ATESTO O RECEBIMENTO PROVISORIO do bem, conforme Art. 140, I, 'a' da Lei 14.133/21, para verificação de conformidade técnica posterior."
                else:
                    texto_atesto = f"ATESTO O RECEBIMENTO DEFINITIVO dos materiais, por estarem em total conformidade com as especificações do Termo de Referência."
                pdf.multi_cell(190, 10, texto_atesto, border=1, align='C', fill=True)
            else:
                pdf.set_font("Arial", 'B', 11)
                pdf.set_text_color(200, 0, 0)
                pdf.multi_cell(190, 10, "DOCUMENTO ENCERRADO COM PENDENCIAS TECNICAS. O ATESTO NAO FOI REALIZADO.", border=1, align='C')
                pdf.set_text_color(0, 0, 0)

            # Assinatura
            pdf.ln(20)
            pdf.cell(190, 10, "________________________________________________", ln=True, align='C')
            pdf.cell(190, 5, f"Servidor Atestante: {servidor_atesta}", ln=True, align='C')
            pdf.set_font("Arial", '', 8)
            pdf.cell(190, 5, f"Relatorio gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')

            pdf_out = pdf.output(dest='S').encode('latin-1', errors='replace')
            st.download_button("📥 Baixar Checklist PDF", data=pdf_out, file_name=f"Checklist_{placa or 'Relatorio'}.pdf")
            
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")

if st.sidebar.button("Novo Recebimento (Limpar)"):
    st.session_state.clear()
    st.rerun()

