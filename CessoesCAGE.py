import streamlit as st
import pandas as pd
from weasyprint import HTML

# Configuração da página Streamlit
st.set_page_config(
    page_title="Gestão de Cessões - CAGE",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Gestão de Cessões de Uso - Relatório Aguarda CAGE")
st.write("Insira a planilha atualizada para filtrar os processos em 'Aguarda CAGE' e gerar o relatório no padrão visual oficial.")

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

def generate_pdf_html(df):
    processes_html = ""
    
    # Agrupa por PROA
    for proa, group in df.groupby('PROA', sort=False):
        items_rows = ""
        for idx, row in group.iterrows():
            entidade = desc_or_empty(row.get('ENTIDADE', '')).upper()
            desc_bem = desc_or_empty(row.get('DESC. BEM 1', '')).upper()
            pat_bem = format_patrimonio(row.get('PAT. BEM 1', ''))
            programa = desc_or_empty(row.get('PROGRAMA/CONVÊNIO', ''))
            termo = desc_or_empty(row.get('N° TERMO', row.get('N TERMO', '')))
            
            # Suporte para múltiplos bens por linha
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
                items_rows += f"""
                <tr>
                    <td class="cell-green-highlight">{entidade}</td>
                    <td class="cell-green-highlight">{desc}</td>
                    <td style="text-align: center; color: #1F2123; font-weight: bold;">{pat}</td>
                    <td style="text-align: left; color: #333333;">{programa}</td>
                    <td style="text-align: center; color: #1F2123; font-weight: bold;">{termo}</td>
                    <td style="text-align: center;"><div class="checkbox-box">✓</div></td>
                    <td style="text-align: center;"><div class="checkbox-box">✓</div></td>
                    <td style="text-align: center;"><div class="checkbox-box">✓</div></td>
                </tr>
                """

        processes_html += f"""
        <div class="proa-block">
            <div class="proa-sidebar"></div>
            <div class="proa-content">
                <div class="proa-header-text">
                    <div class="proa-title">PROA: {proa}</div>
                    <div class="proa-sub">Contagem: {len(group)}</div>
                </div>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th style="width: 18%;">ENTIDADE</th>
                            <th style="width: 26%;">DESC BEM</th>
                            <th style="width: 10%;">PAT BEM</th>
                            <th style="width: 18%;">PROGRAMA / CONVÊNIO</th>
                            <th style="width: 8%;">N° TERMO</th>
                            <th style="width: 7%;">PARECER TÉCNICO</th>
                            <th style="width: 7%;">PARECER AJUR</th>
                            <th style="width: 6%;">ANUÊNCIA</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: A4 portrait;
                margin: 6mm 8mm 8mm 8mm;
                @bottom-right {{
                    content: "Página " counter(page) " de " counter(pages);
                    font-family: Arial, sans-serif;
                    font-size: 7.5pt;
                    color: #555;
                }}
            }}
            
            body {{
                font-family: Arial, Helvetica, sans-serif;
                margin: 0;
                padding: 0;
                font-size: 8pt;
                color: #1F2123;
            }}

            /* Listra RS no Topo */
            .stripe-rs {{
                display: table;
                width: 100%;
                height: 8px;
                margin-bottom: 12px;
            }}
            .stripe-green {{ display: table-cell; background-color: #009246; width: 33.33%; }}
            .stripe-red {{ display: table-cell; background-color: #DA251D; width: 33.33%; }}
            .stripe-yellow {{ display: table-cell; background-color: #FFCC00; width: 33.34%; }}

            .header-title {{
                text-align: center;
                margin-bottom: 14px;
            }}
            .header-title h1 {{
                font-size: 15pt;
                font-weight: bold;
                margin: 0;
                color: #2E6B47;
                letter-spacing: 0.5px;
            }}

            /* Bloco Estruturado com Linha Lateral */
            .proa-block {{
                display: table;
                width: 100%;
                margin-bottom: 12px;
                page-break-inside: avoid;
            }}

            .proa-sidebar {{
                display: table-cell;
                width: 4px;
                background-color: #333333;
            }}

            .proa-content {{
                display: table-cell;
                padding-left: 8px;
            }}

            .proa-header-text {{
                margin-bottom: 4px;
            }}

            .proa-title {{
                font-size: 9.5pt;
                font-weight: bold;
                color: #1F2123;
            }}

            .proa-sub {{
                font-size: 8pt;
                color: #555555;
                margin-left: 10px; /* Indentação */
                margin-top: 1px;
            }}

            .data-table {{
                width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
            }}

            .data-table th, .data-table td {{
                border: 1px solid #E0E0E0;
                padding: 4px 3px;
                vertical-align: middle;
                word-wrap: break-word;
            }}

            /* Cabeçalho Verde Institucional (#2E6B47) com Texto Branco */
            .data-table th {{
                background-color: #2E6B47;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 7pt;
                text-align: center;
                text-transform: uppercase;
                line-height: 1.1;
            }}

            /* Linhas com Fundo Cinza Claro Zebra (#F4F5F7) */
            .data-table tbody tr {{
                background-color: #F4F5F7;
            }}

            /* Texto Verde em Caixa Alta nas Colunas de Destaque */
            .cell-green-highlight {{
                text-align: left;
                color: #2E6B47;
                font-weight: bold;
                font-size: 7.5pt;
            }}

            /* Caixa de Seleção com Check Verde Institucional */
            .checkbox-box {{
                width: 13px;
                height: 13px;
                border: 1.2px solid #2E6B47;
                margin: 0 auto;
                border-radius: 2px;
                background-color: #FFFFFF;
                line-height: 12px;
                font-size: 9pt;
                font-weight: bold;
                color: #2E6B47;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="stripe-rs">
            <div class="stripe-green"></div>
            <div class="stripe-red"></div>
            <div class="stripe-yellow"></div>
        </div>

        <div class="header-title">
            <h1>CESSÕES PARA ANÁLISE</h1>
        </div>

        {processes_html}
    </body>
    </html>
    """
    return html_content

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

                html_str = generate_pdf_html(filtered_df)
                pdf_bytes = HTML(string=html_str).write_pdf()

                st.download_button(
                    label="📄 Baixar Relatório PDF Oficial",
                    data=pdf_bytes,
                    file_name="Cessoes_Aguarda_CAGE.pdf",
                    mime="application/pdf"
                )

    except Exception as e:
        st.error(f"Erro ao processar planilha: {e}")
