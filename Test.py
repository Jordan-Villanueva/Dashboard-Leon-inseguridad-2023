import geopandas as gpd
import folium
from folium import Choropleth
from folium.plugins import MarkerCluster
from shapely import wkt
from streamlit_folium import folium_static
import pandas as pd
import streamlit as st
import ast
import re

# Cargar GeoDataFrame
def load_geo_data():
    result_gdf = pd.read_csv('final-df-Leon.csv')
    result_gdf = result_gdf.drop(columns={'Unnamed: 0'})
    result_gdf['geometry'] = result_gdf['geometry'].apply(wkt.loads)
    result_gdf = gpd.GeoDataFrame(result_gdf)
    result_gdf = result_gdf.set_geometry('geometry')
    result_gdf.crs = "EPSG:4326"
    result_gdf['CP'] = result_gdf['CP'].fillna('Unknown')
    result_gdf = result_gdf[result_gdf['NOMASEN'] != '0']
    dissolved_gdf = result_gdf.dissolve(by='NOMASEN', aggfunc='first').reset_index()
    dissolved_gdf['NOMASEN_STR'] = dissolved_gdf['NOMASEN'].apply(
        lambda x: ", ".join(ast.literal_eval(x)) if isinstance(x, str) else str(x))
    return dissolved_gdf

# Cargar y procesar archivo del trimestre específico
def load_enemar_data(selected_trimestre):
    filename = f'Incidencias-{selected_trimestre}.xlsx'
    enemar = pd.read_excel(filename)

    # Renombrar columnas para distinguir las dos series
    enemar.columns = ['CP', 'COLONIA', 'RACH_1', 'RAN_1', 'RAT_1', 'RDV_1', 'RCV_1',
                      'RACH_2', 'RAN_2', 'RAT_2', 'RDV_2', 'RCV_2', 'FECHA']

    enemar['FECHA'] = pd.to_datetime(enemar['FECHA'], errors='coerce')
    enemar['COLONIA'] = enemar['COLONIA'].str.upper()

    # Sumar columnas dobles
    enemar['RACH'] = enemar['RACH_1'].fillna(0) + enemar['RACH_2'].fillna(0)
    enemar['RAN'] = enemar['RAN_1'].fillna(0) + enemar['RAN_2'].fillna(0)
    enemar['RAT'] = enemar['RAT_1'].fillna(0) + enemar['RAT_2'].fillna(0)
    enemar['RDV'] = enemar['RDV_1'].fillna(0) + enemar['RDV_2'].fillna(0)
    enemar['RCV'] = enemar['RCV_1'].fillna(0) + enemar['RCV_2'].fillna(0)

    # Agrupar y sumar por COLONIA y CP
    suma_rach_por_colonia = enemar.groupby(['COLONIA', 'CP'])[['RACH', 'RAN', 'RAT', 'RDV', 'RCV']].sum().reset_index()

    # Excluir colonias no localizadas o foráneas
    suma_rach_por_colonia = suma_rach_por_colonia[~suma_rach_por_colonia['COLONIA'].isin(['ZONA NO LOCALIZADA', 'ZONA FORÁNEA'])]

    return suma_rach_por_colonia

# Diseño Streamlit
st.title("Robos totales reportados ante FGE y SSPPC por trimestre y colonia en León durante 2023")

selected_trimestre = st.selectbox('Seleccionar trimestre', ['ENE-MAR', 'ABR-JUN', 'JUL-SEP', 'OCT-DIC'], index=0, key='trimestre_selector')

dissolved_gdf = load_geo_data()
suma_rach_por_colonia = load_enemar_data(selected_trimestre)

# Mapear datos de delitos al GeoDataFrame disuelto
for index, row in dissolved_gdf.iterrows():
    nomasen_list = [item.strip("[]() ") for item in ast.literal_eval(row['NOMASEN'])]
    total_rach = total_ran = total_rat = total_rdv = total_rcv = 0

    for colonia in nomasen_list:
        colonia_pattern = re.escape(colonia)
        matching_rows = suma_rach_por_colonia[suma_rach_por_colonia['COLONIA'].str.contains(colonia_pattern)]
        total_rach += matching_rows['RACH'].sum()
        total_ran += matching_rows['RAN'].sum()
        total_rat += matching_rows['RAT'].sum()
        total_rdv += matching_rows['RDV'].sum()
        total_rcv += matching_rows['RCV'].sum()

    dissolved_gdf.at[index, 'RACH'] = total_rach
    dissolved_gdf.at[index, 'RAN'] = total_ran
    dissolved_gdf.at[index, 'RAT'] = total_rat
    dissolved_gdf.at[index, 'RDV'] = total_rdv
    dissolved_gdf.at[index, 'RCV'] = total_rcv

for col in ['RACH','RAN','RAT','RDV','RCV']:
    dissolved_gdf[col] = pd.to_numeric(dissolved_gdf[col], errors='coerce').fillna(0)

selected_column = st.selectbox(
    'Seleccionar tipo de robo: Robo a Casa Habitación (RACH), Robo a Negocio (RAN), Robo a Transeúnte (RAT), Robo de Vehículo (RDV) o Robo con Violencia (RCV)', 
    ['RACH', 'RAN', 'RAT', 'RDV', 'RCV'], index=0, key='selected_column_key')

m = folium.Map(location=[21.1167, -101.6833], tiles='OpenStreetMap', zoom_start=12, attr="My Data attribution")

def create_choropleth(dissolved_gdf, selected_column):
    gdf = dissolved_gdf.copy()
    gdf['NOMASEN_STR'] = gdf['NOMASEN_STR'].astype(str)
    choropleth = Choropleth(
        geo_data=gdf,
        data=gdf,
        columns=['NOMASEN_STR', selected_column],
        key_on='feature.properties.NOMASEN_STR',
        fill_color='plasma',
        fill_opacity=0.8,
        line_opacity=0.01,
        legend_name=selected_column,
        highlight=True
    )
    choropleth.add_to(m)
    folium.GeoJson(
        gdf,
        name="Colonias",
        style_function=lambda x: {"fillOpacity": 0, "color": "transparent"},
        tooltip=folium.GeoJsonTooltip(
            fields=['NOMASEN_STR', selected_column],
            aliases=['Colonias', selected_column],
            localize=True,
            sticky=False
        )
    ).add_to(m)

def create_marker_cluster(dissolved_gdf, selected_column):
    marker_cluster = MarkerCluster().add_to(m)
    for _, row in dissolved_gdf.iterrows():
        centroid = row['geometry'].centroid
        centroid_coordinates = [centroid.y, centroid.x]
        delito_valor = int(row[selected_column]) if pd.notna(row[selected_column]) else 0
        popup_text = f"Colonias: {row['NOMASEN_STR']}<br>{selected_column}: {delito_valor}"
        icon = folium.Icon(color='teal', icon='circle', prefix='fa')
        marker = folium.Marker(location=centroid_coordinates, popup=popup_text, icon=icon)
        marker.add_to(marker_cluster)

create_choropleth(dissolved_gdf, selected_column)
create_marker_cluster(dissolved_gdf, selected_column)

folium_static(m)

st.markdown("""
Datos geográficos obtenidos de [INEGI](https://www.inegi.org.mx/app/ageeml/#) y datos de robos obtenidos del [Observatorio Ciudadano](https://ocl.org.mx/mapa-ocl-org-mx/), de acuerdo a la Fiscalía General del Estado de Guanajuato y la Secretaría de Seguridad, Prevención y Protección Ciudadana.
""")
