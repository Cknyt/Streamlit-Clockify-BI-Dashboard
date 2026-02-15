import streamlit as st
import pandas as pd
import plotly.express as px
import os # NUEVO: Para verificar si existe el archivo

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE USUARIO (LO QUE TÚ EDITAS)
# -----------------------------------------------------------------------------

# 1. RUTA DEL ARCHIVO POR DEFECTO
# Asegúrate de que este archivo exista en tu carpeta de GitHub/Local
ARCHIVO_DEFECTO = "data/reporte_horas.xlsx" 

# 2. PRESUPUESTOS PREDEFINIDOS (Configura aquí tus proyectos)
# Si un proyecto del Excel no está aquí, usará el valor 'DEFAULT_BUDGET'
PRESUPUESTOS_CONFIG = {
    "Proyecto Web App": 1200,
    "Consultoría BI": 500,
    "Mantenimiento": 150,
    "Diseño UX/UI": 300
}
DEFAULT_BUDGET = 100.0

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Dashboard Clockify", page_icon="📊", layout="wide")

@st.cache_data
def load_data(file_path_or_buffer):
    try:
        # Detectar si es un string (ruta local) o un buffer (archivo subido)
        if isinstance(file_path_or_buffer, str):
            ext = file_path_or_buffer.split('.')[-1]
            file_source = file_path_or_buffer
        else:
            ext = file_path_or_buffer.name.split('.')[-1]
            file_source = file_path_or_buffer

        if 'csv' in ext:
            df = pd.read_csv(file_source, parse_dates=['Start Date'], dayfirst=True)
        else:
            df = pd.read_excel(file_source)
        return df
    except Exception as e:
        st.error(f"Error al leer datos: {e}")
        return None

def process_data(df):
    df = df.dropna(subset=['Project'])
    df['Duration (decimal)'] = pd.to_numeric(df['Duration (decimal)'], errors='coerce').fillna(0)
    df['Month_Year'] = df['Start Date'].dt.to_period('M').astype(str)
    return df

def main():
    st.title("📊 Dashboard de Control de Horas")

    # -------------------------------------------------------------------------
    # 1. LÓGICA DE CARGA AUTOMÁTICA VS MANUAL
    # -------------------------------------------------------------------------
    df_raw = None
    
    with st.sidebar:
        st.header("1. Origen de Datos")
        
        # Opción A: Carga manual (por si quieren ver un archivo nuevo temporalmente)
        uploaded_file = st.file_uploader("Actualizar datos (Opcional)", type=["csv", "xlsx"])
        
        if uploaded_file:
            df_raw = load_data(uploaded_file)
            st.success("✅ Usando archivo subido manualmente.")
        
        # Opción B: Carga automática del archivo en el repo
        elif os.path.exists(ARCHIVO_DEFECTO):
            df_raw = load_data(ARCHIVO_DEFECTO)
            st.info(f"📂 Cargando datos predefinidos: {ARCHIVO_DEFECTO}")
        
        else:
            st.warning("⚠️ No se encontró archivo por defecto ni se ha subido uno.")

    # Si tenemos datos, procedemos
    if df_raw is not None:
        df = process_data(df_raw)

        # ---------------------------------------------------------------------
        # 2. PRESUPUESTOS INTELIGENTES
        # ---------------------------------------------------------------------
        st.sidebar.header("2. Ajuste de Presupuestos")
        
        unique_projects = sorted(df['Project'].unique())
        
        # AQUÍ ESTÁ LA MAGIA: Mapeamos tus configuraciones al DataFrame
        budget_data = []
        for proj in unique_projects:
            # Busca en tu diccionario, si no existe usa el default
            horas = PRESUPUESTOS_CONFIG.get(proj, DEFAULT_BUDGET)
            budget_data.append({'Project': proj, 'Horas Contratadas': float(horas)})
            
        budget_template = pd.DataFrame(budget_data)

        # Mostramos el editor, pero ya vendrá con TUS números pre-rellenados
        edited_budget_df = st.data_editor(
            budget_template,
            column_config={
                "Horas Contratadas": st.column_config.NumberColumn(format="%.0f h")
            },
            hide_index=True,
            use_container_width=True,
            key="budget_editor"
        )

        # ---------------------------------------------------------------------
        # 3. RESTO DE LA LÓGICA (Igual que antes)
        # ---------------------------------------------------------------------
        # Filtros
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            all_users = sorted(df['User'].unique())
            sel_users = st.multiselect("Filtrar Usuarios", all_users, default=all_users)
        with col2:
            all_months = sorted(df['Month_Year'].unique())
            sel_months = st.multiselect("Filtrar Meses", all_months, default=all_months)

        # Aplicar filtros
        df_filtered = df[df['User'].isin(sel_users) & df['Month_Year'].isin(sel_months)]
        
        if df_filtered.empty:
            st.warning("Sin datos para mostrar.")
            return

        # Cálculos
        grouped = df_filtered.groupby('Project')['Duration (decimal)'].sum().reset_index()
        grouped.rename(columns={'Duration (decimal)': 'Horas Consumidas'}, inplace=True)
        
        merged = pd.merge(edited_budget_df, grouped, on='Project', how='left').fillna(0)
        merged['Horas Restantes'] = merged['Horas Contratadas'] - merged['Horas Consumidas']
        merged['Estado'] = merged.apply(lambda x: 'Excedido' if x['Horas Restantes'] < 0 else 'OK', axis=1)

        # Gráfico Principal
        fig = px.bar(
            merged.melt(id_vars='Project', value_vars=['Horas Contratadas', 'Horas Consumidas']),
            x='Project', y='value', color='variable', barmode='group',
            color_discrete_map={'Horas Contratadas': '#BDC3C7', 'Horas Consumidas': '#E74C3C'},
            title="Comparativa General"
        )
        st.plotly_chart(fig, use_container_width=True)

        # Tabla Detallada
        st.subheader("Detalle Financiero")
        
        # Formato de columnas
        format_dict = {
            'Horas Contratadas': '{:,.0f}',
            'Horas Consumidas': '{:,.2f}', 
            'Horas Restantes': '{:,.2f}'
        }
        
        st.dataframe(
            merged.style.format(format_dict)
            .apply(lambda x: ['background-color: #ffcccc' if v < 0 else '' for v in x['Horas Restantes']] * len(x), axis=1, subset=pd.IndexSlice[:, :]), 
            use_container_width=True
        )

if __name__ == "__main__":
    main()
