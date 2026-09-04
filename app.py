# -*- coding: utf-8 -*-
"""
Painel de Ações SINOVA MT
=========================

Dashboard interativo (Streamlit) para consulta das ações do SINOVA -
Laboratório de Inovação da SEPLAG/MT.

Os dados são lidos diretamente do Google Sheets (links de exportação CSV),
unificando a base de ações INTERNAS e EXTERNAS em um único DataFrame.

Deploy: Streamlit Community Cloud (app.py + requirements.txt).
"""

import unicodedata

import pandas as pd
import plotly.express as px
import streamlit as st

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# =============================================================================

st.set_page_config(
    page_title="🚀 Painel de Ações SINOVA MT",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# 2. FONTES DE DADOS (GOOGLE SHEETS)
# =============================================================================
# Substitua pelas URLs reais de exportação CSV do seu Google Sheets.
# Formato: https://docs.google.com/spreadsheets/d/<ID_PLANILHA>/export?format=csv&gid=<ID_ABA>
# Importante: a planilha precisa estar compartilhada como
# "Qualquer pessoa com o link - Leitor".

URL_ABA_INTERNO = "https://docs.google.com/spreadsheets/d/1RAfdxYZOQYMGWRnWONSraUWyzh7vSOAyVJTtBMGXz6o/export?format=csv&gid=0"
URL_ABA_EXTERNO = "https://docs.google.com/spreadsheets/d/1RAfdxYZOQYMGWRnWONSraUWyzh7vSOAyVJTtBMGXz6o/export?format=csv&gid=600618779"

# Paleta institucional simples, usada em todos os gráficos.
COR_PRIMARIA = "#1F6FEB"
COR_SECUNDARIA = "#00A88F"
COR_DESTAQUE = "#F2A33C"

# Colunas que o painel espera encontrar após a padronização.
COLUNAS_PADRAO = ["Data", "Produto", "Atividade", "Orgao", "Categoria", "Participantes"]
COLUNAS_TEXTO = ["Produto", "Orgao", "Categoria", "Atividade"]


# =============================================================================
# 3. ETL - CARGA, PADRONIZAÇÃO E LIMPEZA
# =============================================================================

def _normalizar(nome: str) -> str:
    """Normaliza um nome de coluna: maiúsculas, sem acentos e sem espaços extras.

    Deixa o mapeamento tolerante a variações de digitação na planilha
    (ex.: "Nº de Participantes", "N° DE PARTICIPANTES", "ÓRGÃO", "ORGAO").
    """
    # Os indicadores ordinais precisam sair ANTES do NFKD: a decomposição de
    # compatibilidade transformaria "Nº" em "No" e quebraria o mapeamento.
    texto = str(nome)
    for simbolo in ("º", "°", "ª"):
        texto = texto.replace(simbolo, "")
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.upper().split())


# Mapa: nome normalizado da planilha -> nome padronizado no painel.
MAPA_COLUNAS = {
    # Produto (aba INTERNA = "PRODUTOS" / aba EXTERNA = "TIPO")
    "PRODUTOS": "Produto",
    "PRODUTO": "Produto",
    "TIPO": "Produto",
    # Data
    "DATA/MES": "Data",
    "DATA / MES": "Data",
    "DATA": "Data",
    "MES": "Data",
    # Participantes
    "N DE PARTICIPANTES": "Participantes",
    "N. DE PARTICIPANTES": "Participantes",
    "NUMERO DE PARTICIPANTES": "Participantes",
    "PARTICIPANTES": "Participantes",
    # Demais dimensões
    "ORGAO": "Orgao",
    "ORGAOS": "Orgao",
    "CATEGORIA": "Categoria",
    "ATIVIDADE": "Atividade",
}


def _padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia as colunas do DataFrame para o padrão interno do painel."""
    renomear = {}
    for coluna in df.columns:
        chave = _normalizar(coluna)
        renomear[coluna] = MAPA_COLUNAS.get(chave, str(coluna).strip())
    df = df.rename(columns=renomear)
    # Remove colunas duplicadas geradas por cabeçalhos repetidos na planilha.
    return df.loc[:, ~df.columns.duplicated()]


@st.cache_data(ttl=600, show_spinner="Carregando dados do Google Sheets...")
def carregar_dados() -> pd.DataFrame:
    """Lê as duas abas do Google Sheets, unifica e limpa a base.

    Returns:
        DataFrame unificado (`df_full`) já tratado e pronto para os filtros.
    """
    # --- 3.1 Leitura das abas ------------------------------------------------
    # A aba EXTERNA possui uma linha de título extra no topo -> skiprows=1.
    df_interno = pd.read_csv(URL_ABA_INTERNO)
    df_externo = pd.read_csv(URL_ABA_EXTERNO, skiprows=1)

    # --- 3.2 Padronização de colunas -----------------------------------------
    df_interno = _padronizar_colunas(df_interno)
    df_externo = _padronizar_colunas(df_externo)

    # Marca a origem para permitir análises por natureza da ação.
    df_interno["Origem"] = "Interno"
    df_externo["Origem"] = "Externo"

    # --- 3.3 Unificação das bases --------------------------------------------
    df_full = pd.concat([df_interno, df_externo], ignore_index=True, sort=False)

    # Garante a existência de todas as colunas esperadas, mesmo que uma das
    # abas não possua alguma delas.
    for coluna in COLUNAS_PADRAO:
        if coluna not in df_full.columns:
            df_full[coluna] = pd.NA

    # --- 3.4 Limpeza ---------------------------------------------------------
    # Remove linhas totalmente vazias (comuns em planilhas com espaçamento).
    df_full = df_full.dropna(how="all")

    # Data: converte para datetime e cria a chave textual de período.
    df_full["Data"] = pd.to_datetime(df_full["Data"], errors="coerce", dayfirst=True)
    df_full = df_full.dropna(subset=["Data"])
    df_full["MES_ANO"] = df_full["Data"].dt.strftime("%Y-%m")

    # Participantes: numérico, sem nulos e como inteiro.
    df_full["Participantes"] = (
        pd.to_numeric(df_full["Participantes"], errors="coerce").fillna(0).astype(int)
    )

    # Colunas textuais: remove espaços nas pontas e normaliza vazios.
    for coluna in COLUNAS_TEXTO:
        df_full[coluna] = (
            df_full[coluna]
            .astype("string")
            .str.strip()
            .replace({"": pd.NA, "-": pd.NA, "nan": pd.NA})
            .fillna("Não informado")
        )

    return df_full.sort_values("Data").reset_index(drop=True)


def formatar_milhar(valor) -> str:
    """Formata um número inteiro no padrão brasileiro (ex.: 1.234.567)."""
    return f"{int(valor):,}".replace(",", ".")


def grafico_barras_h(dados: pd.DataFrame, x: str, y: str, titulo: str, cor: str):
    """Cria um gráfico de barras horizontal padronizado (Plotly Express)."""
    fig = px.bar(
        dados,
        x=x,
        y=y,
        orientation="h",
        text=x,
        title=titulo,
        color_discrete_sequence=[cor],
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        yaxis=dict(title="", categoryorder="total ascending"),
        xaxis=dict(title=""),
        margin=dict(l=10, r=40, t=60, b=10),
        height=430,
        plot_bgcolor="rgba(0,0,0,0)",
        title_font_size=17,
        showlegend=False,
    )
    return fig


# =============================================================================
# 4. CARGA DOS DADOS
# =============================================================================

st.title("🚀 Painel de Ações SINOVA MT")
st.caption(
    "Laboratório de Inovação da SEPLAG/MT — acompanhamento das ações internas e externas."
)

try:
    df_full = carregar_dados()
except Exception as erro:  # noqa: BLE001 - feedback amigável na interface
    st.error(
        "**Não foi possível carregar os dados do Google Sheets.**\n\n"
        "Verifique se as URLs de exportação CSV estão preenchidas corretamente e "
        "se a planilha está compartilhada como *Qualquer pessoa com o link — Leitor*."
    )
    st.exception(erro)
    st.stop()

if df_full.empty:
    st.warning("A base foi carregada, mas não contém registros válidos.")
    st.stop()


# =============================================================================
# 5. BARRA LATERAL - FILTROS
# =============================================================================

st.sidebar.header("🎛️ Filtros")

produtos_disponiveis = sorted(df_full["Produto"].dropna().unique().tolist())
orgaos_disponiveis = sorted(df_full["Orgao"].dropna().unique().tolist())
meses_disponiveis = sorted(df_full["MES_ANO"].unique().tolist())

produtos_selecionados = st.sidebar.multiselect(
    "Produto",
    options=produtos_disponiveis,
    default=[],
    placeholder="Todos os produtos",
    help="Deixe vazio para considerar todos os produtos.",
)

orgaos_selecionados = st.sidebar.multiselect(
    "Órgão",
    options=orgaos_disponiveis,
    default=[],
    placeholder="Todos os órgãos",
    help="Deixe vazio para considerar todos os órgãos.",
)

# Seletor de intervalo de período (baseado em MES_ANO, no formato AAAA-MM).
if len(meses_disponiveis) > 1:
    periodo_inicio, periodo_fim = st.sidebar.select_slider(
        "Período (mês/ano)",
        options=meses_disponiveis,
        value=(meses_disponiveis[0], meses_disponiveis[-1]),
    )
else:
    periodo_inicio = periodo_fim = meses_disponiveis[0]
    st.sidebar.info(f"Período disponível: **{periodo_inicio}**")

st.sidebar.divider()
if st.sidebar.button("🔄 Atualizar dados", width="stretch"):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption("Fonte: planilha SINOVA no Google Sheets (cache de 10 minutos).")


# --- Aplicação dos filtros ---------------------------------------------------

df_filtrado = df_full[df_full["MES_ANO"].between(periodo_inicio, periodo_fim)].copy()

if produtos_selecionados:
    df_filtrado = df_filtrado[df_filtrado["Produto"].isin(produtos_selecionados)]

if orgaos_selecionados:
    df_filtrado = df_filtrado[df_filtrado["Orgao"].isin(orgaos_selecionados)]

if df_filtrado.empty:
    st.warning(
        "⚠️ Nenhuma ação encontrada para os filtros selecionados. "
        "Ajuste os critérios na barra lateral."
    )
    st.stop()


# =============================================================================
# 6. KPIs EM DESTAQUE
# =============================================================================

col_kpi1, col_kpi2, col_kpi3 = st.columns(3)

col_kpi1.metric(
    "Total de Ações Realizadas",
    formatar_milhar(len(df_filtrado)),
    help="Quantidade de ações registradas no período e filtros selecionados.",
)
col_kpi2.metric(
    "Total de Participações",
    formatar_milhar(df_filtrado["Participantes"].sum()),
    help="Soma do número de participantes de todas as ações filtradas.",
)
col_kpi3.metric(
    "Órgãos Parceiros Envolvidos",
    formatar_milhar(df_filtrado["Orgao"].nunique()),
    help="Quantidade de órgãos distintos presentes na seleção atual.",
)

st.divider()


# =============================================================================
# 7. GRÁFICOS INTERATIVOS
# =============================================================================

col_esq, col_dir = st.columns(2)

# --- Gráfico 1: Ações por Órgão ---------------------------------------------
with col_esq:
    acoes_por_orgao = (
        df_filtrado["Orgao"]
        .value_counts()
        .head(15)
        .rename_axis("Orgao")
        .reset_index(name="Ações")
        .sort_values("Ações", ascending=True)
    )
    st.plotly_chart(
        grafico_barras_h(
            acoes_por_orgao,
            x="Ações",
            y="Orgao",
            titulo="🏛️ Ações por Órgão (Top 15)",
            cor=COR_PRIMARIA,
        ),
        width="stretch",
    )

# --- Gráfico 2: Ações por Categoria -----------------------------------------
with col_dir:
    acoes_por_categoria = (
        df_filtrado["Categoria"]
        .value_counts()
        .rename_axis("Categoria")
        .reset_index(name="Ações")
        .sort_values("Ações", ascending=True)
    )
    st.plotly_chart(
        grafico_barras_h(
            acoes_por_categoria,
            x="Ações",
            y="Categoria",
            titulo="🗂️ Ações por Categoria",
            cor=COR_SECUNDARIA,
        ),
        width="stretch",
    )

# --- Gráfico 3: Top 10 ações mais impactantes -------------------------------
top_acoes = df_filtrado.nlargest(10, "Participantes").copy()

# Rótulo legível: usa a atividade e, quando ausente, o produto.
top_acoes["Ação"] = (
    top_acoes["Atividade"]
    .where(top_acoes["Atividade"] != "Não informado", top_acoes["Produto"])
    .str.slice(0, 60)
)
# Sufixo com mês/ano evita que ações homônimas se sobreponham no eixo.
top_acoes["Ação"] = (
    top_acoes["Ação"] + " (" + top_acoes["Data"].dt.strftime("%m/%Y") + ")"
)
top_acoes = top_acoes.sort_values("Participantes", ascending=True)

st.plotly_chart(
    grafico_barras_h(
        top_acoes,
        x="Participantes",
        y="Ação",
        titulo="🏆 Top 10 Ações Mais Impactantes (por nº de participantes)",
        cor=COR_DESTAQUE,
    ),
    width="stretch",
)


# =============================================================================
# 8. TABELA DETALHADA
# =============================================================================

with st.expander("🔍 Ver dados detalhados da seleção atual"):
    colunas_exibicao = [
        c
        for c in ["Data", "Produto", "Atividade", "Orgao", "Categoria",
                  "Participantes", "Origem"]
        if c in df_filtrado.columns
    ]
    st.dataframe(
        df_filtrado[colunas_exibicao].sort_values("Data", ascending=False),
        width="stretch",
        hide_index=True,
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Participantes": st.column_config.NumberColumn("Participantes", format="%d"),
        },
    )
    st.download_button(
        "⬇️ Baixar seleção em CSV",
        data=df_filtrado[colunas_exibicao].to_csv(index=False).encode("utf-8-sig"),
        file_name="sinova_acoes_filtradas.csv",
        mime="text/csv",
    )
