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

  cells_data = {}

  for elem in root.iter():
    if elem.tag.endswith("managedObject"):
      cls = elem.get("class", "")
      dist_name = elem.get("distName", "")

      if "LNCEL" in dist_name:
        base_match = re.search(r"(LNCEL-\d+)", dist_name)
        if base_match:
          cell_key = base_match.group(1)

          if cell_key not in cells_data:
            mapped_name = cell_key
            for old_c, new_c in cell_mapping.items():
              if old_c == cell_key:
                mapped_name = new_c
                break
            cells_data[cell_key] = {
                "distName_mapped": mapped_name,
                "cell_id": cell_key,
            }

          for p in elem.findall(".//"):
            if p.tag.endswith("p") and "name" in p.attrib:
              param_name = p.get("name")
              param_val = p.text
              if param_name in ["pMax", "dlMimoMode"]:
                cells_data[cell_key][param_name] = param_val

  if not cells_data:
    st.warning("No se encontraron objetos de celda LNCEL en el XML.")
    st.stop()

  df_cells = pd.DataFrame(list(cells_data.values()))

  st.divider()
  st.subheader("🎯 Vista Resumida por Celda (pMax y dlMimoMode)")

  # Asegurar que existan las columnas de parámetros
  for col in ["pMax", "dlMimoMode"]:
    if col not in df_cells.columns:
      df_cells[col] = "N/A"

  # Columnas estrictamente seleccionadas (sin tac ni distName_base)
  display_cols = ["distName_mapped", "pMax", "dlMimoMode", "cell_id"]
  final_cols = [c for c in display_cols if c in df_cells.columns]

  df_cells = df_cells.sort_values(by="distName_mapped")

  st.dataframe(
      df_cells[final_cols], use_container_width=True, hide_index=True
  )

  st.divider()
  st.subheader("📥 Descarga Directa de Datos de Celdas")
  csv_cells = df_cells[final_cols].to_csv(index=False).encode("utf-8")
  st.download_button(
      label="📥 Descargar resumen de celdas en CSV",
      data=csv_cells,
      file_name="resumen_celdas_mimo_pmax.csv",
      mime="text/csv",
  )
