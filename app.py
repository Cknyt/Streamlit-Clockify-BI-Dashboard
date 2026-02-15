import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Dashboard de Control de Horas - Clockify",
    page_icon="📊",
    layout="wide"
)

# -----------------------------------------------------------------------------
# FUNCIONES DE CARGA Y PROCESAMIENTO
# -----------------------------------------------------------------------------

@st.cache_data
def load_data(file):
    """
    Carga el archivo CSV o Excel subido por el usuario.
    Maneja errores de formato y detecta la extensión.
    """
    try:
        if file.name.endswith('.csv'):
            # Clockify a veces usa coma o punto y coma dependiendo de la config regional
            df = pd.read_csv(file, parse_dates=['Start Date'], dayfirst=True)
        else:
            df = pd.read_excel(file)
        return df
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        return None

def validate_columns(df):
    """
    Verifica que las columnas esenciales de Clockify existan.
    Se adapta a nombres comunes ('Project', 'User', 'Duration (decimal)').
    """
    # Ajusta estos nombres si tu export de Clockify tiene headers diferentes
    required_columns = ['Project', 'User', 'Duration (decimal)', 'Start Date']
    
    missing = [col for col in required_columns if col not in df.columns]
    
    if missing:
        st.error(f"⚠️ El archivo no tiene las columnas requeridas: {missing}. Por favor verifica tu exportación.")
        return False
    return True

def process_data(df):
    """
    Limpieza y pre-procesamiento de datos.
    """
    # Eliminar filas donde no haya proyecto asignado (si aplica)
    df = df.dropna(subset=['Project'])
    
    # Asegurar que la duración es numérica
    df['Duration (decimal)'] = pd.to_numeric(df['Duration (decimal)'], errors='coerce').fillna(0)
    
    # Extraer Mes y Año para filtros
    df['Month_Year'] = df['Start Date'].dt.to_period('M').astype(str)
    
    return df

# -----------------------------------------------------------------------------
# INTERFAZ PRINCIPAL
# -----------------------------------------------------------------------------

def main():
    st.title("📊 Dashboard de Gestión de Proyectos & Costes")
    st.markdown("### Análisis de Rentabilidad y Control de Horas (Clockify)")

    # 1. SIDEBAR: CARGA DE DATOS
    with st.sidebar:
        st.header("1. Carga de Datos")
        uploaded_file = st.file_uploader("Sube tu reporte de Clockify (CSV/Excel)", type=["csv", "xlsx"])
        
        st.info("💡 Asegúrate de exportar el reporte 'Detailed' de Clockify con duración decimal.")

    if uploaded_file is not None:
        # Cargar datos
        df_raw = load_data(uploaded_file)

        if df_raw is not None and validate_columns(df_raw):
            df = process_data(df_raw)

            # 2. INPUT DE PRESUPUESTOS (Dinámico)
            st.sidebar.header("2. Presupuestos")
            st.sidebar.markdown("Define las horas contratadas por proyecto:")
            
            # Obtenemos lista única de proyectos
            unique_projects = sorted(df['Project'].unique())
            
            # Creamos un DF temporal para que el usuario edite
            budget_template = pd.DataFrame({
                'Project': unique_projects,
                'Horas Contratadas': [100.0] * len(unique_projects) # Valor por defecto
            })

            # Data Editor permite editar celdas como un Excel dentro de la web
            edited_budget_df = st.data_editor(
                budget_template,
                column_config={
                    "Horas Contratadas": st.column_config.NumberColumn(
                        "Horas Contratadas",
                        help="Presupuesto total en horas",
                        min_value=0,
                        step=1,
                        format="%.1f h"
                    )
                },
                hide_index=True,
                use_container_width=True
            )

            # 3. FILTROS EN PANTALLA
            st.divider()
            col_f1, col_f2, col_f3 = st.columns(3)
            
            with col_f1:
                # Filtro de Meses
                all_months = sorted(df['Month_Year'].unique())
                selected_months = st.multiselect("Filtrar por Mes:", all_months, default=all_months)
            
            with col_f2:
                # Filtro de Usuarios
                all_users = sorted(df['User'].unique())
                selected_users = st.multiselect("Filtrar por Usuario:", all_users, default=all_users)
            
            with col_f3:
                 # Filtro de Proyectos (para visualizar detalle)
                selected_projects_filter = st.multiselect("Filtrar por Proyecto (Visualización):", unique_projects, default=unique_projects)

            # Aplicar filtros al DataFrame principal
            df_filtered = df[
                (df['Month_Year'].isin(selected_months)) & 
                (df['User'].isin(selected_users)) &
                (df['Project'].isin(selected_projects_filter))
            ]

            if df_filtered.empty:
                st.warning("No hay datos para los filtros seleccionados.")
                return

            # -------------------------------------------------------------------------
            # CÁLCULOS DE KPI & BURN-DOWN
            # -------------------------------------------------------------------------
            
            # Agrupar datos filtrados por proyecto
            grouped_df = df_filtered.groupby('Project')['Duration (decimal)'].sum().reset_index()
            grouped_df.rename(columns={'Duration (decimal)': 'Horas Consumidas'}, inplace=True)
            
            # Unir con el presupuesto definido por el usuario (Inner join para mantener integridad)
            merged_df = pd.merge(edited_budget_df, grouped_df, on='Project', how='left').fillna(0)
            
            # Calcular Horas Restantes y Estado
            merged_df['Horas Restantes'] = merged_df['Horas Contratadas'] - merged_df['Horas Consumidas']
            merged_df['% Consumido'] = (merged_df['Horas Consumidas'] / merged_df['Horas Contratadas']) * 100
            
            # Lógica para evitar números negativos en gráficos de partes, pero mantener el dato real
            merged_df['Estado'] = merged_df.apply(lambda x: 'Excedido' if x['Horas Restantes'] < 0 else 'En Presupuesto', axis=1)

            # -------------------------------------------------------------------------
            # VISUALIZACIÓN: KPIs GLOBALES
            # -------------------------------------------------------------------------
            st.subheader("Estado General (Selección Actual)")
            
            total_budget = merged_df[merged_df['Project'].isin(selected_projects_filter)]['Horas Contratadas'].sum()
            total_consumed = merged_df[merged_df['Project'].isin(selected_projects_filter)]['Horas Consumidas'].sum()
            total_remaining = total_budget - total_consumed
            
            kpi1, kpi2, kpi3 = st.columns(3)
            
            kpi1.metric("Horas Totales Consumidas", f"{total_consumed:,.1f} h")
            kpi2.metric("Presupuesto Total", f"{total_budget:,.1f} h")
            
            # Delta color inverse: Si es negativo es malo (rojo)
            kpi3.metric(
                "Balance Total de Horas", 
                f"{total_remaining:,.1f} h", 
                delta_color="normal" if total_remaining >= 0 else "inverse"
            )

            # Barra de progreso general
            if total_budget > 0:
                progreso_total = min(total_consumed / total_budget, 1.0)
                color_bar = "red" if total_consumed > total_budget else "green"
                st.progress(progreso_total, text=f"Consumo Global: {total_consumed/total_budget:.1%}")
            
            st.divider()

            # -------------------------------------------------------------------------
            # VISUALIZACIÓN: GRÁFICOS
            # -------------------------------------------------------------------------
            
            col_chart1, col_chart2 = st.columns([2, 1])

            with col_chart1:
                st.subheader("Comparativa: Presupuesto vs Real")
                
                # Gráfico de Barras Agrupadas
                # Transformamos datos para Plotly (Melting)
                chart_data = merged_df[merged_df['Project'].isin(selected_projects_filter)].melt(
                    id_vars=['Project'], 
                    value_vars=['Horas Contratadas', 'Horas Consumidas'],
                    var_name='Tipo', 
                    value_name='Horas'
                )
                
                fig_bar = px.bar(
                    chart_data, 
                    x='Project', 
                    y='Horas', 
                    color='Tipo', 
                    barmode='group',
                    title="Horas Contratadas vs Consumidas por Proyecto",
                    color_discrete_map={'Horas Contratadas': '#2E86C1', 'Horas Consumidas': '#E74C3C'},
                    text_auto='.1f'
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            with col_chart2:
                st.subheader("Desglose por Usuario")
                # Pie chart de distribución de trabajo
                user_dist = df_filtered.groupby('User')['Duration (decimal)'].sum().reset_index()
                fig_pie = px.pie(
                    user_dist, 
                    values='Duration (decimal)', 
                    names='User', 
                    title="Carga de Trabajo (Horas)",
                    hole=0.4
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            # -------------------------------------------------------------------------
            # TABLA DE DETALLE Y EXPORTACIÓN
            # -------------------------------------------------------------------------
            st.subheader("📋 Detalle de Control Financiero")
            
            # Pivot table para ver Usuarios por Proyecto
            pivot_view = df_filtered.pivot_table(
                index='Project', 
                columns='User', 
                values='Duration (decimal)', 
                aggfunc='sum', 
                fill_value=0,
                margins=True,
                margins_name='Total Proyecto'
            )
            
            # Unir con información de presupuesto (solo para filas de proyectos, no la fila 'Total')
            # Es un poco complejo mezclar pivot con datos estáticos, así que mostraremos dos tablas o una enriquecida.
            # Vamos a mostrar la tabla enriquecida de Merged DF con resaltado.

            # Estilo condicional para la tabla
            def highlight_over_budget(row):
                if row['Horas Restantes'] < 0:
                    return ['background-color: #ffcccc; color: black'] * len(row)
                return [''] * len(row)

            # Preparamos tabla final para mostrar
            display_df = merged_df[merged_df['Project'].isin(selected_projects_filter)].copy()
            display_df = display_df.set_index('Project')
            
            # Formato visual

            # Estilo condicional para la tabla (sin cambios)
            def highlight_over_budget(row):
                # Verificamos que la columna exista y sea numérica antes de comparar
                if 'Horas Restantes' in row and isinstance(row['Horas Restantes'], (int, float)):
                    if row['Horas Restantes'] < 0:
                        return ['background-color: #ffcccc; color: black'] * len(row)
                return [''] * len(row)

            # Preparamos tabla final para mostrar
            display_df = merged_df[merged_df['Project'].isin(selected_projects_filter)].copy()
            
            # Limpiamos columnas que no queremos mostrar o que causan ruido
            cols_to_show = ['Project', 'Horas Contratadas', 'Horas Consumidas', 'Horas Restantes', '% Consumido', 'Estado']
            # Aseguramos que solo seleccionamos columnas que existen
            display_df = display_df[[c for c in cols_to_show if c in display_df.columns]]
            
            display_df = display_df.set_index('Project')
            
            # DEFINIMOS EL FORMATO ESPECÍFICO POR COLUMNA
            # Así evitamos que intente formatear texto como números
            format_dict = {
                'Horas Contratadas': '{:,.2f}',
                'Horas Consumidas': '{:,.2f}',
                'Horas Restantes': '{:,.2f}',
                '% Consumido': '{:.1f}%'
            }

            # Formato visual
            st.dataframe(
                display_df.style
                .apply(highlight_over_budget, axis=1)
                .format(format_dict), # <--- AQUÍ ESTÁ EL CAMBIO CLAVE
                use_container_width=True
            )


            # Exportación a Excel
            st.subheader("📥 Descargar Reporte")
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                display_df.to_excel(writer, sheet_name='Resumen Proyectos')
                pivot_view.to_excel(writer, sheet_name='Detalle Usuarios')
                df_filtered.to_excel(writer, sheet_name='Data Cruda Filtrada', index=False)
                
            st.download_button(
                label="Descargar Excel Procesado",
                data=buffer.getvalue(),
                file_name="reporte_control_costes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        else:
            st.info("Esperando carga de archivo válido...")
    else:
        st.write("👈 Por favor, sube un archivo en la barra lateral para comenzar.")

if __name__ == "__main__":
    main()
