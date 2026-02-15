import streamlit as st
import pandas as pd
import plotly.express as px
import os

# -----------------------------------------------------------------------------
# CONFIGURACIÓN (AQUÍ EDITAS LAS HORAS)
# -----------------------------------------------------------------------------

ARCHIVO_DEFECTO = "data/reporte_horas.csv" 

# DICCIONARIO DE PRESUPUESTOS
# Escribe el nombre EXACTO del proyecto (tal cual sale en Clockify) y sus horas.
PRESUPUESTOS_CONFIG = {
    "BUSTURIALDEA": 2500,
    "Consultoría BI": 500,
    "Mantenimiento": 150,
    "Diseño UX/UI": 300,
    "Migración Datos": 80
}

# Si un proyecto no está en la lista de arriba, se le asignarán estas horas por defecto:
DEFAULT_BUDGET = 100.0

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Dashboard Clockify", page_icon="📊", layout="wide")

# -----------------------------------------------------------------------------
# FUNCIONES
# -----------------------------------------------------------------------------

@st.cache_data
def load_data(file_path_or_buffer):
    try:
        # Detectar si es ruta local o archivo subido
        if isinstance(file_path_or_buffer, str):
            file_source = file_path_or_buffer
            filename = file_path_or_buffer
        else:
            file_source = file_path_or_buffer
            filename = file_path_or_buffer.name

        # Cargar según extensión
        if filename.endswith('.csv'):
            df = pd.read_csv(file_source, parse_dates=['Start Date'], dayfirst=True)
        else:
            df = pd.read_excel(file_source)
        return df
    except Exception as e:
        st.error(f"Error al leer datos: {e}")
        return None

def process_data(df):
    if 'Project' not in df.columns:
        return df
    
    # Limpieza
    df = df.dropna(subset=['Project'])
    if 'Duration (decimal)' in df.columns:
        df['Duration (decimal)'] = pd.to_numeric(df['Duration (decimal)'], errors='coerce').fillna(0)
    
    # Crear columna Mes
    if 'Start Date' in df.columns:
        df['Month_Year'] = df['Start Date'].dt.to_period('M').astype(str)
        
    return df

def highlight_row(row):
    """Pinta la fila de rojo si se excede el presupuesto"""
    try:
        if row['Horas Restantes'] < 0:
            return ['background-color: #ffcccc; color: black'] * len(row)
    except:
        pass
    return [''] * len(row)

# -----------------------------------------------------------------------------
# MAIN APP
# -----------------------------------------------------------------------------

def main():
    st.title("📊 Dashboard de Control de Horas")

    df_raw = None
    
    # --- BARRA LATERAL ---
    with st.sidebar:
        st.header("1. Carga de Datos")
        
        # Carga de archivo
        uploaded_file = st.file_uploader("Subir archivo (Opcional)", type=["csv", "xlsx"])
        
        if uploaded_file:
            df_raw = load_data(uploaded_file)
            st.success("✅ Archivo manual cargado")
        elif os.path.exists(ARCHIVO_DEFECTO):
            df_raw = load_data(ARCHIVO_DEFECTO)
            st.info(f"📂 Datos del repositorio cargados")
        else:
            st.warning("⚠️ No se encuentran datos.")

    # Si hay datos, mostramos el resto
    if df_raw is not None:
        df = process_data(df_raw)

        # --- GESTIÓN DE PRESUPUESTOS ---
        st.sidebar.divider()
        st.sidebar.header("2. Presupuestos")
        
        # Obtenemos proyectos únicos del archivo
        unique_projects = sorted(df['Project'].astype(str).unique())
        
        # Cruzamos con tu configuración manual (PRESUPUESTOS_CONFIG)
        budget_data = []
        for proj in unique_projects:
            # Si el proyecto está en tu lista manual, usa ese valor. Si no, usa el default.
            horas = PRESUPUESTOS_CONFIG.get(proj, DEFAULT_BUDGET)
            budget_data.append({'Project': proj, 'Horas Contratadas': float(horas)})
            
        budget_template = pd.DataFrame(budget_data)

        # Editor visual (por si quieren ajustar algo puntualmente)
        edited_budget_df = st.data_editor(
            budget_template,
            column_config={
                "Horas Contratadas": st.column_config.NumberColumn(format="%.0f h")
            },
            hide_index=True,
            use_container_width=True,
            key="budget_editor"
        )

        # --- FILTROS DE VISUALIZACIÓN (RECUPERADOS) ---
        st.sidebar.divider()
        st.sidebar.header("3. Filtros de Visualización")
        
        # 1. Filtro Proyecto (¡Recuperado!)
        sel_projects = st.sidebar.multiselect(
            "Filtrar Proyectos",
            unique_projects,
            default=unique_projects
        )

        # 2. Filtro Usuarios
        all_users = sorted(df['User'].unique())
        sel_users = st.sidebar.multiselect(
            "Filtrar Usuarios",
            all_users,
            default=all_users
        )

        # 3. Filtro Meses
        all_months = sorted(df['Month_Year'].unique())
        sel_months = st.sidebar.multiselect(
            "Filtrar Meses",
            all_months,
            default=all_months
        )

        # APLICAR FILTROS
        df_filtered = df[
            (df['Project'].isin(sel_projects)) &
            (df['User'].isin(sel_users)) &
            (df['Month_Year'].isin(sel_months))
        ]

        if df_filtered.empty:
            st.warning("No hay datos con los filtros seleccionados.")
            return

        # --- CÁLCULOS ---
        grouped = df_filtered.groupby('Project')['Duration (decimal)'].sum().reset_index()
        grouped.rename(columns={'Duration (decimal)': 'Horas Consumidas'}, inplace=True)
        
        # Unir presupuesto (edited_budget_df) con lo consumido (grouped)
        merged = pd.merge(edited_budget_df, grouped, on='Project', how='left').fillna(0)
        
        # IMPORTANTE: Filtramos también el dataframe 'merged' para que en la tabla
        # solo salgan los proyectos que has seleccionado en el filtro
        merged = merged[merged['Project'].isin(sel_projects)]

        merged['Horas Restantes'] = merged['Horas Contratadas'] - merged['Horas Consumidas']

        # --- GRÁFICOS ---
        st.subheader("Comparativa de Proyectos")
        fig = px.bar(
            merged.melt(id_vars='Project', value_vars=['Horas Contratadas', 'Horas Consumidas']),
            x='Project', y='value', color='variable', barmode='group',
            color_discrete_map={'Horas Contratadas': '#BDC3C7', 'Horas Consumidas': '#E74C3C'}
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- TABLA DETALLE ---
        st.subheader("📋 Detalle Financiero")
        format_dict = {
            'Horas Contratadas': '{:,.0f}',
            'Horas Consumidas': '{:,.2f}', 
            'Horas Restantes': '{:,.2f}'
        }
        
        st.dataframe(
            merged.style
            .format(format_dict)
            .apply(highlight_row, axis=1), 
            use_container_width=True
        )

if __name__ == "__main__":
    main()
