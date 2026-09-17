import re
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Extractor de Configuración XML - RAN",
    page_icon="📡",
    layout="wide",
)

st.title("📡 Extractor de Parámetros de Archivos XML (SCF)")

# Diccionario de mapeo de celdas
cell_mapping = {
    "LNCEL-101": "R1",
    "LNCEL-102": "R2",
    "LNCEL-103": "R3",
    "LNCEL-104": "R4",
    "LNCEL-151": "T1",
    "LNCEL-152": "T2",
    "LNCEL-153": "T3",
    "LNCEL-154": "T4",
    "LNCEL-201": "M1",
    "LNCEL-202": "M2",
    "LNCEL-203": "M3",
    "LNCEL-204": "M4",
    "LNCEL-51": "S1",
    "LNCEL-52": "S2",
    "LNCEL-53": "S3",
    "LNCEL-54": "S4",
    "LNCEL-1": "L1",
    "LNCEL-2": "L2",
    "LNCEL-3": "L3",
    "LNCEL-4": "L4",
    "NRCELL-1": "G1",
    "NRCELL-2": "G2",
    "NRCELL-3": "G3",
}

uploaded_file = st.file_uploader("Sube el archivo XML", type=["xml"])

if uploaded_file is not None:
  try:
    tree = ET.parse(uploaded_file)
    root = tree.getroot()
    st.success("¡Archivo cargado y analizado con éxito!")
  except Exception as e:
    st.error(f"Error al leer el archivo XML: {e}")
    st.stop()

  # 1. Extraer datos agrupados por managedObject
  data = []
  for elem in root.iter():
    if elem.tag.endswith("managedObject"):
      cls = elem.get("class", "")
      dist_name = elem.get("distName", "")

      # Mapeo de celda exacta
      mapped_dist_name = dist_name
      for old_cell, new_cell in cell_mapping.items():
        pattern = r"\b" + re.escape(old_cell) + r"\b"
        if re.search(pattern, dist_name):
          mapped_dist_name = new_cell
          break

      # Extraer todos los parámetros de este objeto en un diccionario
      params = {}
      for p in elem.findall(".//"):
        if p.tag.endswith("p") and "name" in p.attrib:
          params[p.get("name")] = p.text

      data.append(
          {
              "class": cls,
              "distName": dist_name,
              "distName_mapped": mapped_dist_name,
              **params,  # Desempaquetamos los parámetros como columnas individuales
          }
      )

  if not data:
    st.warning("No se encontraron objetos administrados en el XML.")
    st.stop()

  df = pd.DataFrame(data)

  st.divider()
  st.subheader("🎯 Vista Resumida por Celda (con pMax y dlMimoMode)")

  # Filtrar solo objetos que correspondan a celdas mapeadas (opcional, o mostrar todos)
  # Verificamos qué columnas de parámetros existen en el XML
  available_cols = df.columns.tolist()

  # Seleccionar columnas principales a mostrar al inicio
  base_display = ["distName_mapped", "class"]

  # Añadir parámetros clave si existen en el XML
  extra_cols = []
  for col_candidate in ["pMax", "dlMimoMode", "earfcn", "dlEarfcn", "tac"]:
    if col_candidate in available_cols:
      extra_cols.append(col_candidate)

  # Columnas finales organizadas
  display_columns = base_display + extra_cols + ["distName"]

  # Filtrar el DataFrame para mostrar filas que hayan sido mapeadas a celdas cortas (L1, R1, etc.)
  mapped_only_df = df[df["distName_mapped"].isin(cell_mapping.values())]

  if not mapped_only_df.empty:
    st.dataframe(
        mapped_only_df[display_columns], use_container_width=True, hide_index=True
    )
  else:
    st.info("No se encontraron objetos que coincidan con el mapeo de celdas configurado.")
    st.dataframe(df[base_display + ["distName"]], use_container_width=True)

  st.divider()
  st.subheader("📋 Explorador Completo de Todos los Parámetros")
  st.dataframe(df, use_container_width=True)

  # Botón de descarga
  csv = df.to_csv(index=False).encode("utf-8")
  st.download_button(
      label="📥 Descargar tabla completa en CSV",
      data=csv,
      file_name="parametros_celdas_resumen.csv",
      mime="text/csv",
  )
