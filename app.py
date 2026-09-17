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

  data = []
  for elem in root.iter():
    if elem.tag.endswith("managedObject"):
      cls = elem.get("class", "")
      dist_name = elem.get("distName", "")

      mapped_dist_name = dist_name
      for old_cell, new_cell in cell_mapping.items():
        pattern = r"\b" + re.escape(old_cell) + r"\b"
        if re.search(pattern, dist_name):
          mapped_dist_name = new_cell
          break

      params = {}
      for p in elem.findall(".//"):
        if p.tag.endswith("p") and "name" in p.attrib:
          params[p.get("name")] = p.text

      data.append(
          {
              "class": cls,
              "distName": dist_name,
              "distName_mapped": mapped_dist_name,
              **params,
          }
      )

  if not data:
    st.warning("No se encontraron objetos administrados en el XML.")
    st.stop()

  df = pd.DataFrame(data)

  st.divider()
  st.subheader("🎯 Vista Resumida por Celda (LNCEL Principal)")

  # Filtrar estrictamente la clase principal de celdas LTE (NOKLTE:LNCEL) y las mapeadas
  lncel_df = df[
      (df["class"] == "NOKLTE:LNCEL")
      & (df["distName_mapped"].isin(cell_mapping.values()))
  ].copy()

  if not lncel_df.empty:
    # Asegurar que existan las columnas pMax y dlMimoMode para evitar errores si no están
    for col in ["pMax", "dlMimoMode", "tac"]:
      if col not in lncel_df.columns:
        lncel_df[col] = "N/A"

    # Organizar estrictamente el orden de las columnas solicitado
    display_columns = [
        "distName_mapped",
        "pMax",
        "dlMimoMode",
        "class",
        "tac",
        "distName",
    ]
    # Mantener solo las columnas que realmente existan en el DataFrame
    final_cols = [c for c in display_columns if c in lncel_df.columns]

    st.dataframe(
        lncel_df[final_cols], use_container_width=True, hide_index=True
    )
  else:
    st.info("No se encontraron celdas principales NOKLTE:LNCEL con mapeo activo.")

  st.divider()
  st.subheader("📋 Explorador Completo de Todos los Parámetros")
  st.dataframe(df, use_container_width=True)

  csv = df.to_csv(index=False).encode("utf-8")
  st.download_button(
      label="📥 Descargar tabla completa en CSV",
      data=csv,
      file_name="parametros_celdas_resumen.csv",
      mime="text/csv",
  )
