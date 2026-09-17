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

# Diccionario de mapeo (ordenado de claves más largas a más cortas para evitar solapamientos)
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

      # Lógica de mapeo exacta usando expresiones regulares para evitar cruces
      mapped_dist_name = dist_name
      for old_cell, new_cell in cell_mapping.items():
        # Usamos regex para asegurar que coincida exactamente el identificador de celda
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
              "parameters": params,
          }
      )

  if not data:
    st.warning("No se encontraron objetos administrados en el XML.")
    st.stop()

  flat_rows = []
  for item in data:
    base_row = {
        "class": item["class"],
        "distName": item["distName"],
        "distName_mapped": item["distName_mapped"],
    }
    if item["parameters"]:
      for k, v in item["parameters"].items():
        row = base_row.copy()
        row["parameter_name"] = k
        row["parameter_value"] = v
        flat_rows.append(row)
    else:
      flat_rows.append(
          {
              **base_row,
              "parameter_name": "N/A",
              "parameter_value": "N/A",
          }
      )

  df = pd.DataFrame(flat_rows)

  st.divider()
  st.subheader("🎯 Extracción Directa de Parámetro Clave")
  param_search = st.text_input(
      "Nombre exacto o parcial del parámetro a buscar:", value="dlMimoMode"
  )

  if param_search:
    exact_match = df[
        df["parameter_name"].str.contains(param_search, case=False, na=False)
    ]
    if not exact_match.empty:
      st.dataframe(
          exact_match[
              [
                  "distName_mapped",
                  "class",
                  "parameter_name",
                  "parameter_value",
              ]
          ],
          use_container_width=True,
      )
    else:
      st.info(f"No se encontró el parámetro '{param_search}'.")

  st.divider()
  st.subheader("📋 Tabla General de Resultados")
  st.dataframe(
      df[["distName_mapped", "class", "parameter_name", "parameter_value"]],
      use_container_width=True,
  )

  csv = df.to_csv(index=False).encode("utf-8")
  st.download_button(
      label="📥 Descargar resultados en CSV",
      data=csv,
      file_name="parametros_mapeados_correcto.csv",
      mime="text/csv",
  )
