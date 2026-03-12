with st.container():
    st.markdown('<div class="caixa-info">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    edital = c1.text_input("Edital/ARP:", value=st.session_state.dados_auto["edital"])
    fornecedor = c2.text_input("Fornecedor:", value=st.session_state.dados_auto["fornecedor"])
    placa = c1.text_input("Placa / ID:")
    natureza = c2.radio("Natureza:", ["Consumo", "Permanente"], horizontal=True)
    centro_custo = st.text_input("Centro de Custo:", value=st.session_state.dados_auto["centro_custo"]) if natureza == "Permanente" else ""
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="barra-secao">1. CONFERÊNCIA TÉCNICA</div>', unsafe_allow_html=True)

todos_ok = True
for i, item in enumerate(st.session_state.checklist_items):
    with st.container(border=True):
        c_check, c_text = st.columns([0.15, 0.85])
        st.session_state.conferidos[i] = c_check.checkbox("OK", key=f"c_{i}")
        if not st.session_state.conferidos[i]: todos_ok = False
        c_text.write(f"**{item}**")
        foto = st.camera_input(f"Foto {i+1}", key=f"f_{i}")
        if foto: st.session_state.fotos[i] = foto

# Observação Única no Final
obs_geral = ""
if not todos_ok:
    st.warning("⚠️ Descreva as pendências abaixo:")
    obs_geral = st.text_area("Observações / Pendências Detectadas:")

serv_nome = st.text_input("Servidor Responsável:")

# --- GERAÇÃO DO PDF ---
if st.button("🚀 GERAR RELATÓRIO PDF"):
    if not serv_nome: st.error("Informe o servidor.")
    else:
        try:
            pdf = FPDF()
            pdf.set_margins(20, 20, 20)
            pdf.add_page()
            pdf.set_font("Arial", 'B', 14)
            pdf.set_text_color(0, 154, 68)
            pdf.multi_cell(170, 10, f"CHECKLIST - {obj_curto.upper()}", align='C')
            pdf.ln(5)
            
            pdf.set_font("Arial", 'B', 10); pdf.set_text_color(0, 0, 0)
            pdf.cell(170, 8, f"EDITAL/ARP: {edital}", ln=True, border='B')
            pdf.write(8, "FORNECEDOR: "); pdf.set_font("Arial", '', 10); pdf.multi_cell(140, 8, fornecedor.upper())
            pdf.set_font("Arial", 'B', 10); pdf.cell(170, 8, f"PLACA / ID: {placa.upper()}", ln=True)
            if centro_custo:
                pdf.write(8, "C. CUSTO: "); pdf.set_font("Arial", '', 10); pdf.multi_cell(140, 8, centro_custo.upper())
            
            pdf.ln(5)
            pdf.set_fill_color(0, 154, 68); pdf.set_text_color(255, 255, 255)
            pdf.cell(170, 10, " 1. ITENS CONFERIDOS", ln=True, fill=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(3)

            for idx, item_txt in enumerate(st.session_state.checklist_items):
                status = st.session_state.conferidos.get(idx, False)
                # Desenha o ícone Check ou X
                y_atual = pdf.get_y()
                desenhar_icone_check(pdf, 22, y_atual + 1, status)
                
                pdf.set_font("Arial", 'B', 10)
                pdf.set_x(28) # Empurra o texto para não ficar em cima do ícone
                pdf.multi_cell(160, 7, item_txt.encode('latin-1','replace').decode('latin-1'))

                # ADICIONADO facing_mode="environment"
    foto = st.camera_input(f"Foto {i+1}", key=f"f_{i}", facing_mode="environment")
    
    if foto: st.session_state.fotos[i] = foto
                if idx in st.session_state.fotos:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(st.session_state.fotos[idx].getvalue())
                        tmp_path = tmp.name
                    if pdf.get_y() > 180: pdf.add_page()
                    pdf.image(tmp_path, x=35, w=135); pdf.ln(5)
                    os.unlink(tmp_path)
                pdf.ln(2)

            # Finalização
            pdf.ln(10)
            if todos_ok:
                pdf.set_fill_color(245, 245, 245); pdf.set_font("Arial", 'B', 10)
                t = "ATESTO O RECEBIMENTO DEFINITIVO" if natureza == "Consumo" else "ATESTO O RECEBIMENTO PROVISORIO"
                pdf.multi_cell(170, 10, f"{t} do objeto por estar em conformidade com as especificações conferidas.", border=1, align='C', fill=True)
            else:
                pdf.set_font("Arial", 'B', 10); pdf.set_text_color(200, 0, 0)
                pdf.multi_cell(170, 8, f"PENDENCIAS:\n{obs_geral}", border=1, align='L')
                pdf.set_text_color(0, 0, 0)

            pdf.ln(25); pdf.set_font("Arial", 'B', 10); pdf.cell(170, 8, ln=True, align='C')
            pdf.cell(170, 6, f"SERVIDOR: {serv_nome.upper()}", ln=True, align='C')
            
            pdf_bytes = pdf.output(dest='S').encode('latin-1', errors='replace')
            st.download_button("📥 Baixar PDF", data=pdf_bytes, file_name="Checklist.pdf")
        except Exception as e:
            st.error(f"Erro: {e}")





