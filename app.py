import streamlit as st
from groq import Groq
import pdfplumber
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import tempfile
import os
import io
import json
import time
import re
from PIL import Image

# ==========================================
# 1. INICIALIZAÇÃO SEGURA DO ESTADO
# ==========================================
def preparar_estado():
    if "items_lista" not in st.session_state: st.session_state.items_lista = []
    if "cabecalho" not in st.session_state: 
        st.session_state.cabecalho = {"fornecedor": "", "edital": "", "objeto": "", "nf": "", "qtd": "", "placa": "", "unidade": ""}
    if "midia" not in st.session_state: st.session_state.midia = {}
    if "conferidos_status" not in st.session_state: st.session_state.conferidos_status = {}
    if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None
    if "atesto_tipo" not in st.session_state: st.session_state.atesto_tipo = "Definitivo"
    if "texto_pdf" not in st.session_state: st.session_state.texto_pdf = ""

preparar_estado()

# --- CONFIGURAÇÃO DA IA ---
key = st.secrets.get("GROQ_API_KEY", "")
client = Groq(api_key=key) if key else None

# ==========================================
# 2. FUNÇÕES DE APOIO
# ==========================================
def tr(texto):
    """Trata acentuação para PDF Latin-1"""
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def limpar_json_ia(texto):
    """Garante a extração de um JSON válido da resposta da IA"""
    try:
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        return json.loads(match.group(0)) if match else json.loads(texto)
    except: return None

def extrair_dados_ia(texto_extraido):
    """Prompt refinado de auditoria de hardware contra alucinações"""
    prompt = f"""Você é um Engenheiro de Recebimento Técnico Especialista em Auditoria de Bens Públicos.
    Analise o texto do documento e extraia dados para um checklist de CONFERÊNCIA FÍSICA.

    REGRAS RÍGIDAS:
    1. IGNORE: Obrigações contratuais, vigência, regularidade fiscal, multas ou termos jurídicos.
    2. EXTRAIA: Marca, Modelo, Medidas, Potência, Tensão, Cor, Peças e Componentes Reais.
    3. Se o dado não for algo que o fiscal possa TOCAR ou MEDIR fisicamente, NÃO inclua.

    Responda EXCLUSIVAMENTE um JSON puro:
    {{
      "fornecedor": "Nome da Empresa",
      "edital": "Número da ARP/Contrato",
      "objeto": "Descrição Técnica do Item",
      "checklist": ["Especificação 1 encontrada", "Especificação 2 encontrada"]
    }}

    TEXTO DO DOCUMENTO:
    {texto_extraido}"""
    
    if client:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[{"role": "user", "content": prompt}], 
            temperature=0.1
        )
        return limpar_json_ia(res.choices[0].message.content)
    return None

def perguntar_ia(pergunta, contexto):
    """Chatbot de suporte para dúvidas sobre o PDF"""
    if client and contexto:
        prompt = f"Baseado no documento oficial abaixo, responda de forma técnica e curta: {pergunta}\n\nDocumento:\n{contexto}"
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0)
        return res.choices[0].message.content
    return "Sem suporte disponível."

def processar_imagem_pdf(st_image):
    if st_image is None: return None
    temp_path = os.path.join(tempfile.gettempdir(), f"img_{time.time()}_{os.urandom(4).hex()}.jpg")
    img = Image.open(st_image)
    if img.mode != 'RGB': img = img.convert('RGB')
    img.save(temp_path, "JPEG", quality=70)
    return temp_path

def desenhar_check(pdf, x, y, status):
    cor = (99, 157, 49) if status else (227, 6, 19)
    pdf.set_fill_color(*cor); pdf.ellipse(x, y, 5, 5, 'F')
    pdf.set_draw_color(255, 255, 255); pdf.set_line_width(0.4)
    if status:
        pdf.line(x+1.2, y+2.5, x+2.2, y+3.8); pdf.line(x+2.2, y+3.8, x+3.8, y+1.5)
    else:
        pdf.line(x+1.5, y+1.5, x+3.5, y+3.5); pdf.line(x+3.5, y+1.5, x+1.5, y+3.5)
    pdf.set_line_width(0.2); pdf.set_draw_color(0, 0, 0)

# ==========================================
# 3. CLASSE PDF (IDENTIDADE RS)
# ==========================================
class PDFRS(FPDF):
    def __init__(self, status_geral=True):
        super().__init__()
        self.status_geral = status_geral

    def desenhar_faixa_tricolor(self, y_pos):
        h = 6
        self.set_fill_color(99, 157, 49); self.rect(0, y_pos, 70, h, 'F')
        self.set_fill_color(227, 6, 19); self.rect(70, y_pos, 70, h, 'F')
        self.set_fill_color(255, 194, 14); self.rect(140, y_pos, 70, h, 'F')

    def header(self):
        self.desenhar_faixa_tricolor(0)
        self.set_y(10)
        self.set_font("Arial", 'B', 10); self.set_text_color(0)
        self.cell(0, 6, tr("SECRETARIA DA AGRICULTURA, PECUÁRIA, PRODUÇÃO SUSTENTÁVEL E IRRIGAÇÃO"), 0, 1, 'C')
        self.set_font("Arial", 'B', 14)
        titulo = "RELATÓRIO DE RECEBIMENTO TÉCNICO" if self.status_geral else "RELATÓRIO DE DESCONFORMIDADE TÉCNICA"
        self.cell(0, 8, tr(titulo), 0, 1, 'C')

    def footer(self):
        self.set_y(-10); self.desenhar_faixa_tricolor(291)
        self.set_y(-18); self.set_font("Arial", 'I', 7); self.set_text_color(100)
        self.cell(0, 10, tr(f"Página {self.page_no()} / {{nb}}"), 0, 0, 'C')

# ==========================================
# 4. INTERFACE STREAMLIT
# ==========================================
st.set_page_config(page_title="Recebimento RS", layout="centered")
st.title("📋 Checklist Recebimento Técnico RS")

# --- CARGA (ABRE DIRETO NO UPLOAD) ---
if not st.session_state.items_lista:
    pdf_file = st.file_uploader("Suba o PDF do documento (TR, ARP ou Empenho)", type="pdf")
    if pdf_file and st.button("🔍 ANALISAR DOCUMENTO"):
        with st.spinner("IA extraindo dados técnicos reais..."):
            texto = ""
            with pdfplumber.open(pdf_file) as pdf:
                for pg in pdf.pages[:6]: texto += (pg.extract_text() or "") + "\n"
            st.session_state.texto_pdf = texto
            res = extrair_dados_ia(texto)
            if res:
                st.session_state.cabecalho.update(res)
                st.session_state.items_lista = [{"id": time.time() + i, "texto": txt} for i, txt in enumerate(res['checklist'])]
                st.rerun()

# --- TELA DE OPERAÇÃO ---
elif st.session_state.items_lista:
    # 🤖 CHAT SUPORTE
    with st.expander("🤖 Suporte da IA (Dúvidas sobre o PDF)"):
        pergunta = st.text_input("Qual detalhe você quer confirmar no PDF?")
        if st.button("Consultar"):
            st.info(f"**IA:** {perguntar_ia(pergunta, st.session_state.texto_pdf)}")

    st.markdown(f'<div style="background-color: #639d31; color: white; padding: 10px; border-radius: 5px; font-weight: bold; text-align: center; margin-bottom: 20px;">ITEM: {st.session_state.cabecalho["objeto"].upper()}</div>', unsafe_allow_html=True)

    with st.container(border=True):
        st.write("### 📝 Dados do Processo (Editáveis)")
        c1, c2 = st.columns(2)
        st.session_state.cabecalho["fornecedor"] = c1.text_input("Fornecedor:", value=st.session_state.cabecalho["fornecedor"])
        st.session_state.cabecalho["edital"] = c2.text_input("ARP/Edital:", value=st.session_state.cabecalho["edital"])
        st.session_state.cabecalho["objeto"] = st.text_area("Descrição do Item:", value=st.session_state.cabecalho["objeto"], height=70)
        
        st.session_state.cabecalho["nf"] = c1.text_input("Nº Nota Fiscal:", value=st.session_state.cabecalho["nf"])
        st.session_state.cabecalho["qtd"] = c2.text_input("Quantidade:", value=st.session_state.cabecalho["qtd"])
        st.session_state.cabecalho["placa"] = c1.text_input("ID/Patrimônio:", value=st.session_state.cabecalho["placa"])
        st.session_state.cabecalho["unidade"] = c2.text_input("Unidade de Destino:", value=st.session_state.cabecalho["unidade"])
        st.session_state.atesto_tipo = st.selectbox("Tipo de Atesto no PDF:", ["Definitivo", "Provisório"])

    st.write("### ✅ Itens de Conferência")
    todos_ok = True
    for i, item_obj in enumerate(st.session_state.items_lista):
        uid = item_obj["id"]
        with st.container(border=True):
            col_ch, col_tx, col_ex = st.columns([0.15, 0.7, 0.15])
            st.session_state.conferidos_status[uid] = col_ch.checkbox("OK", key=f"ch_{uid}", value=st.session_state.conferidos_status.get(uid, False))
            if not st.session_state.conferidos_status[uid]: todos_ok = False
            item_obj["texto"] = col_tx.text_input(f"Itm {uid}", value=item_obj["texto"], key=f"input_{uid}", label_visibility="collapsed")
            if col_ex.button("🗑️", key=f"del_{uid}"): st.session_state.items_lista.pop(i); st.rerun()
            
            if uid not in st.session_state.registros_media:
                t1, t2 = st.tabs(["📸 Câmera", "📁 Galeria"])
                with t1:
                    if st.session_state.camera_ativa == uid:
                        f = st.camera_input("Capturar", key=f"cam_{uid}")
                        if f: st.session_state.registros_media[uid] = f; st.session_state.camera_ativa = None; st.rerun()
                    elif st.button("Abrir Câmera", key=f"btn_c_{uid}"): st.session_state.camera_ativa = uid; st.rerun()
                with t2:
                    up = st.file_uploader("Upload", key=f"up_{uid}")
                    if up: st.session_state.registros_media[uid] = up; st.rerun()
            else:
                st.image(st.session_state.registros_media[uid], width=150)
                if st.button("Remover Foto", key=f"rm_{uid}"): del st.session_state.registros_media[uid]; st.rerun()

    if st.button("➕ Adicionar Requisito"):
        st.session_state.items_lista.append({"id": time.time(), "texto": "Novo requisito"})
        st.rerun()

    obs_geral = st.text_area("Observações Gerais / Justificativa:")
    servidor = st.text_input("Nome do Servidor (Atestante):")

    # --- 5. GERAÇÃO DO PDF OTIMIZADO ---
    if st.button("🚀 GERAR RELATÓRIO FINAL"):
        if not servidor: st.error("Informe o servidor.")
        else:
            try:
                pdf = PDFRS(status_geral=todos_ok); pdf.alias_nb_pages(); pdf.set_margins(15, 10, 15)
                cab = st.session_state.cabecalho
                
                # Coleta campos preenchidos
                campos = []
                if cab["fornecedor"]: campos.append(("FORNECEDOR", cab["fornecedor"].upper()))
                if cab["edital"]: campos.append(("ARP/EDITAL", cab["edital"]))
                if cab["nf"]: campos.append(("NOTA FISCAL", cab["nf"]))
                if cab["qtd"]: campos.append(("QUANTIDADE", cab["qtd"]))
                if cab["placa"]: campos.append(("ID/PATR.", cab["placa"].upper()))
                if cab["unidade"]: campos.append(("UNIDADE DESTINO", cab["unidade"].upper()))

                pdf.add_page()
                pdf.set_fill_color(99, 157, 49); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 10)
                pdf.multi_cell(0, 8, tr(f" ITEM: {cab['objeto'].upper()}"), 1, 'L', fill=True)
                
                pdf.set_text_color(0); pdf.set_font("Arial", '', 9); pdf.set_fill_color(245)
                for l, v in campos:
                    pdf.set_font("Arial", 'B', 9); pdf.write(7, tr(f" {l}: "))
                    pdf.set_font("Arial", '', 9); pdf.multi_cell(0, 7, tr(v), 'B', 'L', False)
                pdf.ln(4)

                for it in st.session_state.items_lista:
                    if pdf.get_y() > 240: pdf.add_page()
                    desenhar_check(pdf, 17, pdf.get_y()+1, st.session_state.conferidos_status.get(it['id'], False))
                    pdf.set_x(25); pdf.set_font("Arial", 'B', 10); pdf.multi_cell(165, 6, tr(it['texto']))
                    
                    if it['id'] in st.session_state.registros_media:
                        p = processar_imagem_pdf(st.session_state.registros_media[it['id']])
                        with Image.open(p) as img: p_h = 60 * (img.height/img.width)
                        if pdf.get_y() + p_h > 270: pdf.add_page()
                        pdf.image(p, x=75, y=pdf.get_y()+1, w=50); pdf.set_y(pdf.get_y() + p_h + 4); os.unlink(p)
                    pdf.ln(2); pdf.set_draw_color(220); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(2)

                if pdf.get_y() > 220: pdf.add_page()
                pdf.ln(5); at_cor = (235, 245, 235) if todos_ok else (255, 230, 230)
                pdf.set_fill_color(*at_cor); pdf.set_font("Arial", 'B', 10)
                msg = f"ATESTO O RECEBIMENTO {st.session_state.atesto_tipo.upper()} por conformidade técnica." if todos_ok else "RELATÓRIO DE DESCONFORMIDADE: Itens não atendem aos requisitos."
                pdf.multi_cell(0, 10, tr(msg), 1, 'C', fill=True)

                if obs_geral:
                    pdf.ln(4); pdf.set_font("Arial", 'B', 9); pdf.cell(0, 6, tr("OBSERVAÇÕES:"), 0, 1); pdf.multi_cell(0, 5, tr(obs_geral), 1)

                pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, tr(servidor.upper()), 0, 1, 'C')
                pdf.set_font("Arial", '', 9); pdf.cell(0, 5, tr("Responsável pelo Recebimento"), 0, 1, 'C')

                st.download_button("📥 Baixar PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="Relatorio_RS.pdf", mime="application/pdf")
            except Exception as e: st.error(f"Erro no PDF: {e}")

if st.sidebar.button("Nova Inspeção"): st.session_state.clear(); st.rerun()
