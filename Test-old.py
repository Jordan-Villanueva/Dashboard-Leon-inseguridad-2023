import geopandas as gpd
import folium
from folium import Choropleth
from folium.plugins import MarkerCluster
from shapely import wkt
from streamlit_folium import folium_static
import pandas as pd
import streamlit as st

# Cargar el GeoDataFrame desde el archivo CSV
result_gdf = pd.read_csv('final-df-Leon.csv')
result_gdf = result_gdf.drop(columns={'Unnamed: 0'})
result_gdf['geometry'] = result_gdf['geometry'].apply(wkt.loads)
result_gdf = gpd.GeoDataFrame(result_gdf)

# Establecer la columna de geometría activa
result_gdf = result_gdf.set_geometry('geometry')

# Establecer un CRS en el GeoDataFrame
result_gdf.crs = "EPSG:4326"

# Manejar NaN en la columna 'CP'
result_gdf['CP'] = result_gdf['CP'].fillna('Unknown')
result_gdf = result_gdf[result_gdf['NOMASEN'] != '0']

# Dissolver polígonos basados en el identificador 'NOMASEN'
# excepto cuando el 'NOMASEN' es cero
dissolved_gdf = result_gdf.dissolve(by='NOMASEN', aggfunc='first').reset_index()

# Diseño de la aplicación
st.title("Robos totales reportados ante FGE y SSPPC por trimestre y colonia en León durante 2023")

# Obtener el nombre del archivo según el trimestre seleccionado
selected_trimestre = st.selectbox('Seleccionar trimestre', ['ENE-MAR', 'ABR-JUN', 'JUL-SEP', 'OCT-DIC'], index=0)
filename = f'Incidencias-{selected_trimestre}.xlsx'

# Cargar el nuevo DataFrame desde el archivo correspondiente
enemar = pd.read_excel(filename)
enemar['COLONIA'] = enemar['COLONIA'].str.upper()

# Agrupar y sumar por colonias en el nuevo DataFrame
suma_rach_por_colonia = enemar.groupby(['COLONIA', 'CP'])[['RACH', 'RACH.1', 'RAN', 'RAN.1', 'RAT', 'RAT.1', 'RDV', 'RDV.1', 'RCV', 'RCV.1']].sum().reset_index()
suma_rach_por_colonia = suma_rach_por_colonia[suma_rach_por_colonia['COLONIA'] != 'ZONA NO LOCALIZADA']
suma_rach_por_colonia = suma_rach_por_colonia[suma_rach_por_colonia['COLONIA'] != 'ZONA FORÁNEA']

# Sumar horizontalmente las columnas y guardar los resultados en columnas correspondientes
suma_rach_por_colonia['RACH'] = suma_rach_por_colonia['RACH'] + suma_rach_por_colonia['RACH.1']
suma_rach_por_colonia['RAN'] = suma_rach_por_colonia['RAN'] + suma_rach_por_colonia['RAN.1']
suma_rach_por_colonia['RAT'] = suma_rach_por_colonia['RAT'] + suma_rach_por_colonia['RAT.1']
suma_rach_por_colonia['RDV'] = suma_rach_por_colonia['RDV'] + suma_rach_por_colonia['RDV.1']
suma_rach_por_colonia['RCV'] = suma_rach_por_colonia['RCV'] + suma_rach_por_colonia['RCV.1']

# Eliminar las columnas innecesarias
suma_rach_por_colonia = suma_rach_por_colonia.drop(columns=['RACH.1', 'RAN.1', 'RAT.1', 'RDV.1', 'RCV.1'])

import ast
import re

# Iterar sobre las filas de dissolved_gdf
for index, row in dissolved_gdf.iterrows():
    # Convertir la cadena NOMASEN a una lista de elementos
    nomasen_list = [item.strip("[]()") for item in ast.literal_eval(row['NOMASEN'])]

    # Inicializar las variables totales para cada fila de dissolved_gdf
    total_rach = 0
    total_ran = 0
    total_rat = 0
    total_rdv = 0
    total_rcv = 0

    # Iterar sobre cada colonia en la lista NOMASEN
    for colonia in nomasen_list:
        # Escape any special characters in colonia
        colonia_pattern = re.escape(colonia)

        # Filtrar las filas de suma_rach_por_colonia donde COLONIA está en la lista NOMASEN
        matching_rows = suma_rach_por_colonia[suma_rach_por_colonia['COLONIA'].str.contains(colonia_pattern)]

        # Sumar los valores correspondientes para las filas filtradas y para los CP correspondientes
        total_rach += matching_rows['RACH'].sum()
        total_ran += matching_rows['RAN'].sum()
        total_rat += matching_rows['RAT'].sum()
        total_rdv += matching_rows['RDV'].sum()
        total_rcv += matching_rows['RCV'].sum()

    # Actualizar los valores en dissolved_gdf para las filas donde NOMASEN coincide
    dissolved_gdf.at[index, 'RACH'] = total_rach
    dissolved_gdf.at[index, 'RAN'] = total_ran
    dissolved_gdf.at[index, 'RAT'] = total_rat
    dissolved_gdf.at[index, 'RDV'] = total_rdv
    dissolved_gdf.at[index, 'RCV'] = total_rcv

# Configurar el mapa
m = folium.Map(location=[21.1167, -101.6833], tiles='OpenStreetMap', zoom_start=12, attr="My Data attribution")

# Añadir el Choropleth para la variación de colores según la columna seleccionada
selected_column_key = 'selected_column_key'  # Asigna un valor único a key
selected_column = st.selectbox('Seleccionar tipo de robo: Robo a Casa Habitación (RACH), Robo a Negocio (RAN), Robo a Transeúnte (RAT), Robo de Vehículo (RDV) o Robo con Violencia (RCV)', ['RACH', 'RAN', 'RAT', 'RDV', 'RCV'], index=0, key=selected_column_key)

Choropleth(
    geo_data=dissolved_gdf,
    data=dissolved_gdf,
    columns=['NOMASEN', selected_column],
    key_on='feature.properties.NOMASEN',
    fill_color='plasma',
    fill_opacity=0.8,
    line_opacity=0.01,
    legend_name=selected_column,
    highlight=True,
    tooltip=folium.GeoJsonTooltip(fields=['NOMASEN', selected_column], aliases=['NOMASEN', selected_column], localize=True, sticky=False)
).add_to(m)

# Crear el cluster de marcadores
marker_cluster = MarkerCluster().add_to(m)

# Añadir marcadores para los centroides
for index, row in dissolved_gdf.iterrows():
    centroid = row['geometry'].centroid
    centroid_coordinates = [centroid.y, centroid.x]
    centroid_popup_text = f"NOMASEN: {row['NOMASEN']}, {selected_column}: {row[selected_column]}"

    # Definir un marcador personalizado con icono de Font Awesome
    icon = folium.Icon(color='teal', icon='circle', prefix='fa')
    marker = folium.Marker(
        location=centroid_coordinates,
        popup=centroid_popup_text,
        icon=icon
    )

    # Ajustar el tamaño del icono (puede experimentar con el parámetro 'icon_size')
    marker.options.update({'icon_size': [10, 10]})

    marker.add_to(marker_cluster)

# Mostrar el mapa
folium_static(m)


# Add citation
st.markdown("Created by Jordan Ortiz on February 29th, 2024. Datos geograficos obtenidos de [INEGI](https://www.inegi.org.mx/app/ageeml/#) y datos de robos obtenidos del [Observatorio Ciudadano ](https://ocl.org.mx/mapa-ocl-org-mx/), de acuerdo a la Fiscalía General del Estado de Guanajuato y la Secretaría de Seguridad, Prevención y Protección Ciudadana")
