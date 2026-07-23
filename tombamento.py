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
from PIL import Image

# --- 1. CONFIGURAÇÃO ---
if "GROQ_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GROQ_API_KEY"]
else:
    CHAVE_API = ""

client = Groq(api_key=CHAVE_API) if CHAVE_API else None

# --- 2. FUNÇÕES DE APOIO ---
def tr(texto):
    if not texto: return ""
    return str(texto).encode('latin-1', 'replace').decode('latin-1')

def extrair_patrimonios_ia(pdf_file):
    """Extrai patrimônios de forma otimizada para evitar erro de cota (429/413)"""
    todos_patrimonios = []
    
    with pdfplumber.open(pdf_file) as pdf:
        # Processa o PDF em blocos de 5 páginas para não estourar o limite do Groq
        for i in range(0, len(pdf.pages), 5):
            bloco_texto = ""
            for pagina in pdf.pages[i:i+5]:
                bloco_texto += (pagina.extract_text() or "") + "\n"
            
            if not bloco_texto.strip():
                continue

            prompt = f"""Extraia apenas os Números de Patrimônio deste texto. 
            Ignore qualquer outro texto. Retorne APENAS uma lista JSON de strings: ["num1", "num2"]
            Texto: {bloco_texto[:8000]}""" # Limita caracteres por bloco

            try:
                res = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                resposta = res.choices[0].message.content
                match = re.search(r'\[.*\]', resposta, re.DOTALL)
                if match:
                    lista_bloco = json.loads(match.group(0))
                    todos_patrimonios.extend(lista_bloco)
                time.sleep(1) # Respiro para a API
            except Exception as e:
                st.warning(f"Erro ao processar bloco de páginas {i+1}: {e}")
                continue
                
    # Remove duplicatas e retorna DataFrame
    final_list = list(set([str(p).strip() for p in todos_patrimonios if len(str(p)) > 3]))
    return pd.DataFrame({"PATRIMONIO": final_list})

def salvar_imagem_temp(foto_st):
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    temp.write(foto_st.getvalue())
    temp.close() 
    return temp.name

# --- 3. CLASSE PDF (ESTILO RS) ---
class RelatorioTombamento(FPDF):
    def desenhar_faixa_tricolor(self, y_pos):
        h_faixa = 6
        self.set_fill_color(99, 157, 49); self.rect(0, y_pos, 70, h_faixa, 'F')
        self.set_fill_color(227, 6, 19); self.rect(70, y_pos, 70, h_faixa, 'F')
        self.set_fill_color(255, 194, 14); self.rect(140, y_pos, 70, h_faixa, 'F')

    def header(self):
        self.desenhar_faixa_tricolor(0)
        if self.page_no() == 1:
            self.set_y(10); self.set_font("Arial", 'B', 14); self.set_text_color(0)
            self.cell(0, 10, tr("RELATÓRIO DE TOMBAMENTO PATRIMONIAL"), 0, 1, 'C')
            self.ln(2)
        else: self.set_y(10)

    def footer(self):
        self.set_y(-10); self.desenhar_faixa_tricolor(291)
        self.set_y(-18); self.set_font("Arial", 'I', 7); self.set_text_color(100)
        self.cell(0, 10, tr(f"Página {self.page_no()}"), 0, 0, 'C')

# --- 4. INTERFACE ---
import re # Necessário para o regex de limpeza
st.set_page_config(page_title="Tombamento Master", layout="centered")

if "df_patris" not in st.session_state: st.session_state.df_patris = pd.DataFrame()
if "registros" not in st.session_state: st.session_state.registros = {}
if "desc_lote" not in st.session_state: st.session_state.desc_lote = ""
if "camera_ativa" not in st.session_state: st.session_state.camera_ativa = None

st.title("🛡️ Tombamento Digital")

# --- 5. FASE 1: CARGA ---
if st.session_state.df_patris.empty:
    st.subheader("Configurar Novo Lote")
    st.session_state.desc_lote = st.text_area("Descrição Única do Bem (Ex: Trator Agrícola):", height=80)
    
    t1, t2 = st.tabs(["📄 Extrair PDF", "📊 Colar Lista"])
    with t1:
        file = st.file_uploader("Upload da Relação", type="pdf")
        if file and client and st.button("Analisar PDF com IA"):
            with st.spinner("IA extraindo números... Por ser uma lista longa, pode levar até 1 minuto."):
                try:
                    st.session_state.df_patris = extrair_patrimonios_ia(file)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro crítico: {e}. Tente usar a aba 'Colar Lista' para arquivos muito pesados.")
    with t2:
        txt = st.text_area("Cole os números de patrimônio (um por linha):")
        if st.button("Carregar Lista Manual"):
            st.session_state.df_patris = pd.DataFrame({"PATRIMONIO": [l.strip() for l in txt.split('\n') if l.strip()]})
            st.rerun()

# --- 6. FASE 2: REVISÃO ---
elif not st.session_state.get("iniciado"):
    st.subheader("Revisar Números")
    st.write(f"**Item:** {st.session_state.desc_lote}")
    st.session_state.df_patris = st.data_editor(st.session_state.df_patris, num_rows="dynamic", use_container_width=True)
    if st.button("🚀 Iniciar Operação"):
        st.session_state.iniciado = True; st.rerun()

# --- 7. FASE 3: OPERAÇÃO ---
elif st.session_state.get("iniciado") and not st.session_state.get("finalizado"):
    st.markdown(f'<div style="background-color:#009A44;color:white;padding:10px;border-radius:5px;text-align:center;">{st.session_state.desc_lote.upper()}</div>', unsafe_allow_html=True)
    
    st.write(f"📊 **Registrados:** {len(st.session_state.registros)} de {len(st.session_state.df_patris)}")
    busca = st.text_input("SCANEAR PLAQUETA:", key="input_scan").strip()
    
    if busca:
        if busca in st.session_state.df_patris["PATRIMONIO"].astype(str).values:
            st.success(f"✅ PATRIMÔNIO LOCALIZADO: {busca}")
            serial = st.text_input("Número de Série:", key=f"s_{busca}")
            
            c1, c2 = st.columns(2)
            with c1:
                if f"f1_{busca}" not in st.session_state:
                    if st.button("📷 Foto Plaqueta"): st.session_state.camera_ativa = f"f1_{busca}"; st.rerun()
                    if st.session_state.camera_ativa == f"f1_{busca}":
                        f = st.camera_input("Plaqueta", key=f"cam1_{busca}")
                        if f: st.session_state[f"f1_{busca}"] = f; st.session_state.camera_ativa = None; st.rerun()
                else:
                    st.image(st.session_state[f"f1_{busca}"], width=120)
                    if st.button("🗑️ Apagar Foto 1", key=f"d1_{busca}"): del st.session_state[f"f1_{busca}"]; st.rerun()

            with c2:
                if f"f2_{busca}" not in st.session_state:
                    if st.button("📷 Foto do Bem"): st.session_state.camera_ativa = f"f2_{busca}"; st.rerun()
                    if st.session_state.camera_ativa == f"f2_{busca}":
                        f = st.camera_input("Geral", key=f"cam2_{busca}")
                        if f: st.session_state[f"f2_{busca}"] = f; st.session_state.camera_ativa = None; st.rerun()
                else:
                    st.image(st.session_state[f"f2_{busca}"], width=120)
                    if st.button("🗑️ Apagar Foto 2", key=f"d2_{busca}"): del st.session_state[f"f2_{busca}"]; st.rerun()

            if st.button("💾 SALVAR E PRÓXIMO", key=f"save_{busca}"):
                if f"f2_{busca}" in st.session_state:
                    st.session_state.registros[busca] = {"placa": busca, "serial": serial, "f1": st.session_state[f"f1_{busca}"], "f2": st.session_state[f"f2_{busca}"]}
                    st.rerun()
        else: st.error("Número não encontrado na lista carregada.")

    if st.session_state.registros:
        st.write("---")
        st.write("### 📋 Lançados")
        for p in list(st.session_state.registros.keys()):
            col_inf, col_ex = st.columns([0.8, 0.2])
            col_inf.write(f"**P:** {p} | **S:** {st.session_state.registros[p]['serial']}")
            if col_ex.button("🗑️", key=f"del_{p}"): del st.session_state.registros[p]; st.rerun()

    st.divider()
    if st.button("🏁 Finalizar e Gerar PDF"): st.session_state.finalizado = True; st.rerun()

# --- 8. FASE FINAL: PDF ---
elif st.session_state.get("finalizado"):
    servidor = st.text_input("Responsável:")
    setor = st.text_input("Unidade de Destino:")
    obs_finais = st.text_area("Observações:")
    
    if st.button("🚀 BAIXAR TERMO OFICIAL"):
        try:
            pdf = RelatorioTombamento(); pdf.alias_nb_pages(); pdf.set_margins(15, 10, 15)
            lista = list(st.session_state.registros.items())
            for i, (placa, dados) in enumerate(lista):
                if i % 2 == 0: pdf.add_page()
                else:
                    pdf.ln(5); pdf.set_draw_color(200); pdf.line(15, pdf.get_y(), 195, pdf.get_y()); pdf.ln(5)

                pdf.set_fill_color(99, 157, 49); pdf.set_text_color(255); pdf.set_font("Arial", 'B', 10)
                pdf.multi_cell(0, 8, tr(f" ITEM: {st.session_state.desc_lote.upper()}"), 1, 'L', fill=True)
                pdf.set_text_color(0); pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(240)
                pdf.cell(90, 8, tr(f" PATRIMÔNIO: {placa}"), border=1, fill=True)
                pdf.cell(90, 8, tr(f" SÉRIE: {dados['serial']}"), border=1, ln=True, fill=True)
                pdf.cell(0, 8, tr(f" UNIDADE: {setor.upper()}"), border=1, ln=True)
                pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(99, 157, 49)
                pdf.cell(90, 6, tr("EVIDÊNCIA DA PLAQUETA"), 0, 0, 'C'); pdf.cell(90, 6, tr("VISTA GERAL DO BEM"), 0, 1, 'C')
                
                p1 = salvar_imagem_temp(dados["f1"]); p2 = salvar_imagem_temp(dados["f2"])
                y_f = pdf.get_y()
                if p1: pdf.image(p1, x=25, y=y_f, w=70, h=52); os.unlink(p1)
                if p2: pdf.image(p2, x=115, y=y_f, w=70, h=52); os.unlink(p2)
                
                pdf.set_y(y_f + 54); pdf.set_font("Arial", 'I', 8); pdf.set_text_color(0)
                pdf.multi_cell(0, 5, tr("ATESTO O RECEBIMENTO DEFINITIVO do bem acima por estar em conformidade física."), 0, 'C')
                
                if i == len(lista) - 1:
                    if obs_finais:
                        if pdf.get_y() > 220: pdf.add_page()
                        pdf.ln(5); pdf.set_font("Arial", 'B', 9); pdf.cell(0, 6, tr("OBSERVAÇÕES:"), 0, 1); pdf.multi_cell(0, 5, tr(obs_finais), 1)
                    if pdf.get_y() > 240: pdf.add_page()
                    pdf.ln(10); pdf.set_font("Arial", 'B', 11); pdf.cell(0, 6, tr(servidor.upper()), 0, 1, 'C')
                    pdf.set_font("Arial", '', 9); pdf.cell(0, 5, tr("Responsável pelo Tombamento"), 0, 1, 'C')

            st.download_button("📥 Clique para Salvar", data=pdf.output(dest='S').encode('latin-1'), file_name="Termo.pdf")
        except Exception as e: st.error(f"Erro: {e}")

if st.sidebar.button("Limpar Tudo"): st.session_state.clear(); st.rerun()
