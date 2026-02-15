import streamlit as st
import pandas as pd
import plotly.express as px
import os

# -----------------------------------------------------------------------------
# CONFIGURACIÓN
# -----------------------------------------------------------------------------

# CORRECCIÓN 1: Apuntamos al .csv que tienes en GitHub
ARCHIVO_DEFECTO = "data/reporte_horas.csv" 

# Configura aquí tus presupuestos
PRESUPUESTOS_CONFIG = {
    "Proyecto Web App": 1200,
    "Consultoría BI": 500,
    "Mantenimiento": 150,
    "Diseño UX/UI": 300
}
DEFAULT_BUDGET = 100.0

st.set_page_config(page_title="Dashboard Clockify", page_icon="📊", layout="wide")

# -----------------------------------------------------------------------------
# FUNCIONES
# -----------------------------------------------------------------------------

@st.cache_data
def load_data(file_path_or_buffer):
    try:
        # Detectar extensión
        if isinstance(file_path_or_buffer, str):
            # Es una ruta de archivo (carga automática)
            filename = file_path_or_buffer
            file_source = file_path_or_buffer
        else:
            # Es un archivo subido (carga manual)
            filename = file_path_or_buffer.name
            file_source = file_path_or_buffer

        if filename.endswith('.csv'):
            # Clockify suele usar comas, pero a veces punto y coma. 
            # Si falla, prueba cambiar sep=',' a sep=';'
            df = pd.read_csv(file_source, parse_dates=['Start Date'], dayfirst=True)
        else:
            df = pd.read_excel(file_source)
        return df
    except Exception as e:
        st.error(f"Error al leer datos: {e}")
        return None

def process_data(df):
    # Limpieza básica
    if 'Project' not in df.columns:
        st.error("El archivo no tiene columna 'Project'")
        return df
        
    df = df.dropna(subset=['Project'])
    
    # Convertir duración a numérico
    if 'Duration (decimal)' in df.columns:
        df['Duration (decimal)'] = pd.to_numeric(df['Duration (decimal)'], errors='coerce').fillna(0)
    
    # Crear columna Mes-Año
    if 'Start Date' in df.columns:
        df['Month_Year'] = df['Start Date'].dt.to_period('M').astype(str)
        
    return df

# CORRECCIÓN 2: Función de estilo robusta (sin lambdas complejos)
def highlight_row(row):
    """
    Pinta la fila de rojo suave si las horas restantes son negativas.
    """
    try:
        val = row['Horas Restantes']
        # Si es negativo, color rojo para toda la fila
        if pd.notnull(val) and val < 0:
            return ['background-color: #ffcccc; color: black'] * len(row)
    except KeyError:
        pass
    # Si no, fondo por defecto
    return [''] * len(row)

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

def main():
    st.title("📊 Dashboard de Control de Horas")

    # 1. CARGA DE DATOS
    df_raw = None
    
    with st.sidebar:
        st.header("Origen de Datos")
        
        # Prioridad 1: Archivo subido manualmente
        uploaded_file = st.file_uploader("Subir archivo nuevo (Opcional)", type=["csv", "xlsx"])
        
        if uploaded_file:
            df_raw = load_data(uploaded_file)
            st.success("✅ Usando archivo manual.")
            
        # Prioridad 2: Archivo en el repositorio (GitHub)
        elif os.path.exists(ARCHIVO_DEFECTO):
            df_raw = load_data(ARCHIVO_DEFECTO)
            st.info(f"📂 Usando datos del repositorio: {ARCHIVO_DEFECTO}")
        
        else:
            st.warning(f"⚠️ No se encuentra '{ARCHIVO_DEFECTO}' en el repositorio.")

    if df_raw is not None:
        df = process_data(df_raw)

        # 2. PRESUPUESTOS
        st.sidebar.divider()
        st.sidebar.header("Presupuestos")
        
        unique_projects = sorted(df['Project'].astype(str).unique())
        
        budget_data = []
        for proj in unique_projects:
            horas = PRESUPUESTOS_CONFIG.get(proj, DEFAULT_BUDGET)
            budget_data.append({'Project': proj, 'Horas Contratadas': float(horas)})
            
        budget_template = pd.DataFrame(budget_data)

        edited_budget_df = st.data_editor(
            budget_template,
            column_config={
                "Horas Contratadas": st.column_config.NumberColumn(format="%.0f h")
            },
            hide_index=True,
            use_container_width=True,
            key="budget_editor"
        )

        # 3. FILTROS Y PROCESAMIENTO
        # (Solo mostramos filtros si hay columnas para ello)
        if 'User' in df.columns and 'Month_Year' in df.columns:
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                all_users = sorted(df['User'].astype(str).unique())
                sel_users = st.multiselect("Usuarios", all_users, default=all_users)
            with col2:
                all_months = sorted(df['Month_Year'].unique())
                sel_months = st.multiselect("Meses", all_months, default=all_months)

            df_filtered = df[df['User'].isin(sel_users) & df['Month_Year'].isin(sel_months)]
        else:
            df_filtered = df

        if df_filtered.empty:
            st.warning("Sin datos para mostrar con los filtros actuales.")
            return

        # Agrupación
        grouped = df_filtered.groupby('Project')['Duration (decimal)'].sum().reset_index()
        grouped.rename(columns={'Duration (decimal)': 'Horas Consumidas'}, inplace=True)
        
        merged = pd.merge(edited_budget_df, grouped, on='Project', how='left').fillna(0)
        merged['Horas Restantes'] = merged['Horas Contratadas'] - merged['Horas Consumidas']
        
        # 4. VISUALIZACIÓN
        
        # Gráfico
        fig = px.bar(
            merged.melt(id_vars='Project', value_vars=['Horas Contratadas', 'Horas Consumidas']),
            x='Project', y='value', color='variable', barmode='group',
            color_discrete_map={'Horas Contratadas': '#BDC3C7', 'Horas Consumidas': '#E74C3C'},
            title="Comparativa General"
        )
        st.plotly_chart(fig, use_container_width=True)

        # Tabla de Detalle
        st.subheader("📋 Detalle Financiero")
        
        # Definimos formato numérico
        format_dict = {
            'Horas Contratadas': '{:,.0f}',
            'Horas Consumidas': '{:,.2f}', 
            'Horas Restantes': '{:,.2f}'
        }
        
        # Aplicamos estilo con la nueva función robusta
        st.dataframe(
            merged.style
            .format(format_dict)
            .apply(highlight_row, axis=1), 
            use_container_width=True
        )

if __name__ == "__main__":
    main()
