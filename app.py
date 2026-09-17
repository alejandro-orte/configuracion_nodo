import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Extractor de Configuración XML - RAN",
    page_icon="📡",
    layout="wide",
)

st.title("📡 Extractor de Parámetros de Archivos XML (SCF)")
st.write(
    "Sube tu archivo de configuración XML de la estación base (ej. formato Nokia/MRBTS) para buscar, filtrar y extraer parámetros específicos."
)

# 1. Subir archivo
uploaded_file = st.file_uploader("Sube el archivo XML", type=["xml"])

if uploaded_file is not None:
  # Parsear el XML
  try:
    tree = ET.parse(uploaded_file)
    root = tree.getroot()
    st.success("¡Archivo cargado y analizado con éxito!")
  except Exception as e:
    st.error(f"Error al leer el archivo XML: {e}")
    st.stop()

  # 2. Extraer datos de los managedObjects
  data = []
  for elem in root.iter():
    if elem.tag.endswith("managedObject"):
      cls = elem.get("class", "")
      dist_name = elem.get("distName", "")

      # Buscar parámetros <p> dentro del managedObject
      params = {}
      for p in elem.findall(".//"):
        if p.tag.endswith("p") and "name" in p.attrib:
          params[p.get("name")] = p.text

      data.append(
          {"class": cls, "distName": dist_name, "parameters": params}
      )

  if not data:
    st.warning("No se encontraron objetos administrados (`managedObject`) en el XML.")
    st.stop()

  # Convertir a DataFrame plano para facilitar filtros
  flat_rows = []
  for item in data:
    base_row = {"class": item["class"], "distName": item["distName"]}
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
  st.subheader("🔍 Filtros de Búsqueda")

  col1, col2 = st.columns(2)

  with col1:
    # Filtro por clase (ej. NOKLTE:LNCEL_FDD)
    classes_available = df["class"].unique().tolist()
    selected_class = st.selectbox(
        "Filtrar por Clase (`class`)", options=["Todas"] + classes_available
    )

  with col2:
    # Filtro por texto en distName (ej. LNCEL-1)
    search_dist = st.text_input(
        "Buscar en Ruta / DistName (ej. LNCEL-1, MRBTS-426):"
    )

  # Aplicar filtros
  filtered_df = df.copy()
  if selected_class != "Todas":
    filtered_df = filtered_df[filtered_df["class"] == selected_class]
  if search_dist:
    filtered_df = filtered_df[
        filtered_df["distName"].str.contains(search_dist, case=False, na=False)
    ]

  # Mostrar resultados específicos solicitados (ej. dlMimoMode)
  st.subheader("🎯 Extracción Directa de Parámetro Clave")
  param_search = st.text_input(
      "Nombre exacto o parcial del parámetro a buscar (ej. dlMimoMode):",
      value="dlMimoMode",
  )

  if param_search:
    exact_match = df[
        df["parameter_name"].str.contains(param_search, case=False, na=False)
    ]
    if not exact_match.empty:
      st.dataframe(
          exact_match[["distName", "class", "parameter_name", "parameter_value"]],
          use_container_width=True,
      )
    else:
      st.info(f"No se encontró el parámetro '{param_search}' con los filtros actuales.")

  st.divider()
  st.subheader("📋 Tabla General de Resultados Filtrados")
  st.dataframe(filtered_df, use_container_width=True)

  # Botón de descarga de resultados filtrados en CSV
  csv = filtered_df.to_csv(index=False).encode("utf-8")
  st.download_button(
      label="📥 Descargar resultados filtrados en CSV",
      data=csv,
      file_name="parametros_extraidos.csv",
      mime="text/csv",
  )