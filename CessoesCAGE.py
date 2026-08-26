import streamlit as st
import pandas as pd
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm

st.set_page_config(
    page_title="Gestão de Cessões - CAGE",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Gestão de Cessões de Uso - Relatório Aguarda CAGE")
st.write("Insira a planilha atualizada para filtrar os processos e gerar o relatório no padrão visual oficial.")

uploaded_file = st.file_uploader("Selecione a planilha (.csv ou .xlsx)", type=["csv", "xlsx"])

def format_patrimonio(val):
    if pd.isna(val) or str(val).strip() == "":
        return ""
    try:
        return f"{int(float(val)):09d}"
    except:
        return str(val)

def desc_or_empty(val):
    return str(val) if pd.notna(val) else ""

def generate_pdf_reportlab(df):
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=8*mm,
        rightMargin=8*mm,
        topMargin=8*mm,
        bottomMargin=10*mm
    )
    
    story = []
    
    # Cores
    VERDE_INST = colors.HexColor("#2E6B47")
    CINZA_TEXTO = colors.HexColor("#1F2123")
    CINZA_ZEBRA = colors.HexColor("#F4F5F7")
    CINZA_BORDA = colors.HexColor("#E0E0E0")
    CINZA_BARRA = colors.HexColor("#333333")
    VERDE_RS = colors.HexColor("#009246")
    VERMELHO_RS = colors.HexColor("#DA251D")
    AMARELO_RS = colors.HexColor("#FFCC00")
    
    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle(
        'HeaderTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=VERDE_INST,
        alignment=1,
        spaceAfter=10
    )
    
    style_proa_title = ParagraphStyle(
        'ProaTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=CINZA_TEXTO,
        spaceAfter=1
    )
    
    style_proa_sub = ParagraphStyle(
        'ProaSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        textColor=colors.HexColor("#555555"),
        spaceAfter=6
    )
    
    style_th = ParagraphStyle(
        'TH',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.5,
        textColor=colors.white,
        alignment=1
    )
    
    style_td_green = ParagraphStyle(
        'TDGreen',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        textColor=VERDE_INST
    )
    
    style_td_dark = ParagraphStyle(
        'TDDark',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        textColor=CINZA_TEXTO,
        alignment=1
    )

    style_td_text = ParagraphStyle(
        'TDText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        textColor=CINZA_TEXTO
    )
    
    style_check = ParagraphStyle(
        'TDCheck',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=VERDE_INST,
        alignment=1
    )

    # 1. Listra do RS no Topo
    stripe_table = Table(
        [['', '', '']],
        colWidths=[64*mm, 64*mm, 66*mm],
        rowHeights=[2.5*mm]
    )
    stripe_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), VERDE_RS),
        ('BACKGROUND', (1,0), (1,0), VERMELHO_RS),
        ('BACKGROUND', (2,0), (2,0), AMARELO_RS),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(stripe_table)
    story.append(Spacer(1, 4*mm))
    
    # 2. Título Central
    story.append(Paragraph("CESSÕES PARA ANÁLISE", style_title))
    story.append(Spacer(1, 2*mm))

    # Larguras das colunas
    col_w = [33*mm, 48*mm, 18*mm, 33*mm, 16*mm, 11*mm, 11*mm, 11*mm]

    # 3. Processos por PROA
    for proa, group in df.groupby('PROA', sort=False):
        block_elements = []
        
        block_elements.append(Paragraph(f"PROA: {proa}", style_proa_title))
        block_elements.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;Contagem: {len(group)}", style_proa_sub))
        
        table_data = [
            [
                Paragraph("ENTIDADE", style_th),
                Paragraph("DESC BEM", style_th),
                Paragraph("PAT BEM", style_th),
                Paragraph("PROGRAMA / CONVÊNIO", style_th),
                Paragraph("N° TERMO", style_th),
                Paragraph("PARECER<br/>TÉCNICO", style_th),
                Paragraph("PARECER<br/>AJUR", style_th),
                Paragraph("ANUÊNCIA", style_th)
            ]
        ]
        
        for idx, row in group.iterrows():
            entidade = desc_or_empty(row.get('ENTIDADE', '')).upper()
            desc_bem = desc_or_empty(row.get('DESC. BEM 1', '')).upper()
            pat_bem = format_patrimonio(row.get('PAT. BEM 1', ''))
            programa = desc_or_empty(row.get('PROGRAMA/CONVÊNIO', ''))
            termo = desc_or_empty(row.get('N° TERMO', row.get('N TERMO', '')))
            
            bens = []
            if pd.notna(row.get('DESC. BEM 1')) and str(row.get('DESC. BEM 1')).strip() != '':
                bens.append((str(row.get('DESC. BEM 1')).upper(), format_patrimonio(row.get('PAT. BEM 1', ''))))
            if 'DESC. BEM 2' in row and pd.notna(row.get('DESC. BEM 2')) and str(row.get('DESC. BEM 2')).strip() != '':
                bens.append((str(row.get('DESC. BEM 2')).upper(), format_patrimonio(row.get('PAT. BEM 2', ''))))
            if 'DESC. BEM 3' in row and pd.notna(row.get('DESC. BEM 3')) and str(row.get('DESC. BEM 3')).strip() != '':
                bens.append((str(row.get('DESC. BEM 3')).upper(), format_patrimonio(row.get('PAT. BEM 3', ''))))

            if not bens:
                bens = [(desc_bem, pat_bem)]

            for desc, pat in bens:
                table_data.append([
                    Paragraph(entidade, style_td_green),
                    Paragraph(desc, style_td_green),
                    Paragraph(pat, style_td_dark),
                    Paragraph(programa, style_td_text),
                    Paragraph(termo, style_td_dark),
                    Paragraph("✓", style_check),
                    Paragraph("✓", style_check),
                    Paragraph("✓", style_check)
                ])

        t = Table(table_data, colWidths=col_w)
        
        ts = [
            ('BACKGROUND', (0,0), (-1,0), VERDE_INST),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, CINZA_BORDA),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LEFTPADDING', (0,0), (-1,-1), 2),
            ('RIGHTPADDING', (0,0), (-1,-1), 2),
        ]
        
        for r_idx in range(1, len(table_data)):
            ts.append(('BACKGROUND', (0, r_idx), (-1, r_idx), CINZA_ZEBRA))
            
        t.setStyle(TableStyle(ts))
        
        # Tabela envelopadora com a barra lateral esquerda
        proa_table = Table([[Paragraph("", style_td_text), t]], colWidths=[2*mm, 188*mm])
        proa_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), CINZA_BARRA),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        
        block_elements.append(proa_table)
        block_elements.append(Spacer(1, 4*mm))
        
        story.append(KeepTogether(block_elements))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        andamento_cols = [c for c in df.columns if 'ANDAMENTO' in str(c).upper()]

        if not andamento_cols:
            st.error("Coluna 'ANDAMENTO' não foi encontrada na planilha inserida.")
        else:
            col_name = andamento_cols[0]
            filtered_df = df[df[col_name].astype(str).str.strip().str.upper() == 'AGUARDA CAGE'].copy()

            if filtered_df.empty:
                st.warning("Nenhum processo com status 'Aguarda CAGE' foi encontrado na planilha.")
            else:
                st.success(f"Encontrados **{len(filtered_df)}** processos no andamento **Aguarda CAGE**!")

                st.dataframe(
                    filtered_df[['PROA', 'N° TERMO', 'ENTIDADE', 'DESC. BEM 1', 'PAT. BEM 1']],
                    use_container_width=True
                )

                pdf_bytes = generate_pdf_reportlab(filtered_df)

                st.download_button(
                    label="📄 Baixar Relatório PDF Oficial",
                    data=pdf_bytes,
                    file_name="Cessoes_Aguarda_CAGE.pdf",
                    mime="application/pdf"
                )

    except Exception as e:
        st.error(f"Erro ao processar planilha: {e}")
