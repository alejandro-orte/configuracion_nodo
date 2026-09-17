from html.parser import HTMLParser
import io
import re
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Validador XML vs Plan BSS",
    page_icon="📡",
    layout="wide",
)

st.title("📡 Validador y Comparador: XML vs Plan BSS")

# Parser nativo de HTML usando solo bibliotecas estándar de Python (sin dependencias externas)
class HTMLTableParser(HTMLParser):

  def __init__(self):
    super().__init__()
    self.tables = []
    self.current_table = []
    self.current_row = []
    self.current_cell = []
    self.in_table = False
    self.in_row = False
    self.in_cell = False

  def handle_starttag(self, tag, attrs):
    if tag == "table":
      self.in_table = True
      self.current_table = []
    elif tag == "tr" and self.in_table:
      self.in_row = True
      self.current_row = []
    elif tag in ["th", "td"] and self.in_row:
      self.in_cell = True
      self.current_cell = []

  def handle_endtag(self, tag):
    if tag == "table" and self.in_table:
      self.in_table = False
      self.tables.append(self.current_table)
    elif tag == "tr" and self.in_row:
      self.in_row = False
      self.current_table.append(self.current_row)
    elif tag in ["th", "td"] and self.in_cell:
      self.in_cell = False
      text = "".join(self.current_cell).strip()
      self.current_row.append(text)

  def handle_data(self, data):
    if self.in_cell:
      self.current_cell.append(data)


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

col_up1, col_up2 = st.columns(2)
with col_up1:
  xml_file = st.file_uploader("Sube el archivo XML de configuración", type=["xml"])
with col_up2:
  xls_file = st.file_uploader("Sube el archivo Plan BSS", type=["xls", "xlsx"])

if xml_file is not None and xls_file is not None:
  try:
    # 1. Parsear XML
    tree = ET.parse(xml_file)
    root = tree.getroot()

    cells_data = {}
    for elem in root.iter():
      if elem.tag.endswith("managedObject"):
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
                  "Sector": mapped_name,
                  "cell_id": cell_key,
              }

            for p in elem.findall(".//"):
              if p.tag.endswith("p") and "name" in p.attrib:
                param_name = p.get("name")
                param_val = p.text
                if param_name in ["pMax", "dlMimoMode"]:
                  cells_data[cell_key][f"XML_{param_name}"] = param_val

    df_xml = pd.DataFrame(list(cells_data.values()))

    # 2. Parsear Plan BSS (Soporta Excel real o tablas HTML usando el parser nativo de Python)
    bytes_data = xls_file.read()
    df_xls = None

    try:
      # Intentar primero como Excel nativo (.xlsx / .xls binario)
      df_xls = pd.read_excel(io.BytesIO(bytes_data))
    except Exception:
      # Si falla, interpretarlo como tabla HTML usando HTMLParser nativo
      try:
        html_content = bytes_data.decode("utf-8", errors="ignore")
        parser = HTMLTableParser()
        parser.feed(html_content)
        if parser.tables:
          table_data = parser.tables[0]
          df_xls = pd.DataFrame(table_data[1:], columns=table_data[0])
        else:
          raise ValueError("No se encontraron tablas HTML en el archivo.")
      except Exception as e_html:
        st.error(f"No se pudo leer el archivo Plan BSS: {e_html}")
        st.stop()

    # Normalizar nombres de columnas a minúsculas
    df_xls.columns = [str(col).strip().lower() for col in df_xls.columns]

    if "sector" in df_xls.columns and "power" in df_xls.columns:
      df_xls["Sector"] = df_xls["sector"].astype(str).str.strip()

      # Limpiar el punto del power (ej: "42.3" -> "423" y extraer antes del '&' si aplica)
      df_xls["Excel_pMax"] = (
          df_xls["power"]
          .astype(str)
          .str.replace(".", "", regex=False)
          .str.split("&")
          .str[0]
          .str.strip()
      )

      # Manejar columna mimo si existe
      mimo_col = "mimo" if "mimo" in df_xls.columns else None
      if mimo_col:
        df_xls["Excel_dlMimoMode"] = df_xls[mimo_col].fillna("").astype(str).str.strip()
      else:
        df_xls["Excel_dlMimoMode"] = ""

      df_plan = df_xls[["Sector", "Excel_pMax", "Excel_dlMimoMode"]].drop_duplicates(
          subset=["Sector"]
      )

      # 3. Cruzar XML y Plan BSS por Sector
      merged_df = pd.merge(df_xml, df_plan, on="Sector", how="inner")

      if merged_df.empty:
        st.warning(
            "No se encontraron sectores coincidentes entre el XML y el Plan BSS. Revisa los nombres de los sectores."
        )
      else:
        # Normalizar valores para comparación
        merged_df["XML_pMax"] = (
            merged_df.get("XML_pMax", pd.Series([None] * len(merged_df)))
            .astype(str)
            .str.strip()
        )
        merged_df["Excel_pMax"] = merged_df["Excel_pMax"].astype(str).str.strip()

        merged_df["XML_dlMimoMode"] = (
            merged_df.get("XML_dlMimoMode", pd.Series([""] * len(merged_df)))
            .fillna("")
            .astype(str)
            .str.strip()
        )
        merged_df["Excel_dlMimoMode"] = (
            merged_df["Excel_dlMimoMode"].fillna("").astype(str).str.strip()
        )

        # Evaluaciones de igualdad
        merged_df["pMax_Igual"] = merged_df["XML_pMax"] == merged_df["Excel_pMax"]
        merged_df["Mimo_Igual"] = (
            merged_df["XML_dlMimoMode"] == merged_df["Excel_dlMimoMode"]
        )

        st.divider()
        st.subheader("🔍 Resultados de la Comparación (XML vs Plan BSS)")

        display_table = merged_df[
            [
                "Sector",
                "XML_pMax",
                "Excel_pMax",
                "pMax_Igual",
                "XML_dlMimoMode",
                "Excel_dlMimoMode",
                "Mimo_Igual",
            ]
        ].rename(
            columns={
                "Sector": "Sector",
                "XML_pMax": "XML pMax",
                "Excel_pMax": "Excel Power (Sin punto)",
                "pMax_Igual": "pMax Coincide?",
                "XML_dlMimoMode": "XML MIMO",
                "Excel_dlMimoMode": "Excel MIMO",
                "Mimo_Igual": "MIMO Coincide?",
            }
        )

        def color_matching(col):
          return [
              (
                  "background-color: #d4edda"
                  if val
                  else "background-color: #f8d7da"
              )
              for val in col
          ]

        st.dataframe(
            display_table.style.apply(
                color_matching, subset=["pMax_Igual", "Mimo_Igual"]
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.subheader("📥 Descargar Reporte de Comparación")
        csv_data = display_table.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Descargar Comparativa en CSV",
            data=csv_data,
            file_name="comparacion_xml_planbss.csv",
            mime="text/csv",
        )

    else:
      st.error(
          "El archivo Plan BSS no contiene las columnas requeridas 'sector' y 'power'."
      )

  except Exception as e:
    st.error(f"Ocurrió un error al procesar los archivos: {e}")
else:
  st.info(
      "Por favor, sube ambos archivos (el XML de configuración y el Plan BSS) para iniciar la comparación."
  )
