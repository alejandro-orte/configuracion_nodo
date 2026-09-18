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


# Parser nativo de HTML usando solo bibliotecas estándar de Python
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


# Función de mapeo inteligente de sectores
def get_mapped_sector(cell_key):
  match_g = re.match(r"GNCEL-(\d+)", cell_key)
  if match_g:
    return match_g.group(1)

  match_w = re.match(r"WNCEL-(\d+)", cell_key)
  if match_w:
    last_digit = cell_key[-1]
    if last_digit == "1":
      return "X"
    elif last_digit == "2":
      return "Y"
    elif last_digit == "3":
      return "Z"
    return None

  match_nr = re.match(r"NRCELL-(\d+)", cell_key)
  if match_nr:
    num = int(match_nr.group(1))
    if 1 <= num <= 20:
      return f"G{num}"
    return None

  match_l = re.match(r"LNCEL-(\d+)", cell_key)
  if match_l:
    num = int(match_l.group(1))
    if 1 <= num <= 50:
      return f"L{num}"
    elif 51 <= num <= 100:
      return f"S{num - 50}"
    elif 101 <= num <= 150:
      return f"R{num - 100}"
    elif 151 <= num <= 200:
      return f"T{num - 150}"
    elif 201 <= num <= 250:
      return f"M{num - 200}"

  return None


col_up1, col_up2 = st.columns(2)
with col_up1:
  xml_file = st.file_uploader("Sube el archivo XML de configuración", type=["xml"])
with col_up2:
  xls_file = st.file_uploader("Sube el archivo Plan BSS", type=["xls", "xlsx"])

st.divider()

# Botón para iniciar la comparación solo cuando ambos archivos estén listos
if xml_file is not None and xls_file is not None:
  if st.button("🚀 Comparar", type="primary"):
    try:
      with st.spinner("Procesando y comparando archivos..."):
        # 1. Parsear XML
        tree = ET.parse(xml_file)
        root = tree.getroot()

        cells_data = {}
        antenna_mapping = {}

        for elem in root.iter():
          if elem.tag.endswith("managedObject"):
            dist_name = elem.get("distName", "")

            if any(
                k in dist_name for k in ["LNCEL", "NRCELL", "WNCEL", "GNCEL"]
            ):
              base_match = re.search(
                  r"((?:LNCEL|NRCELL|WNCEL|GNCEL)-\d+)", dist_name
              )
              if base_match:
                cell_key = base_match.group(1)
                mapped_name = get_mapped_sector(cell_key)

                if mapped_name:
                  if cell_key not in cells_data:
                    cells_data[cell_key] = {
                        "Sector": mapped_name,
                        "cell_id": cell_key,
                    }

                  for p in elem.findall(".//"):
                    if p.tag.endswith("p") and "name" in p.attrib:
                      param_name = p.get("name")
                      param_val = p.text
                      if (
                          param_val
                          and param_val.strip().upper() != "LIBRE"
                      ):
                        if param_name in [
                            "pMax",
                            "maxCarrierPower",
                            "perTrxPower",
                        ]:
                          cells_data[cell_key]["XML_pMax"] = param_val
                        elif param_name == "dlMimoMode":
                          cells_data[cell_key]["XML_dlMimoMode"] = param_val

            ant_model = None
            sector_id_val = None

            for p in elem.findall(".//"):
              if p.tag.endswith("p") and "name" in p.attrib:
                if p.get("name") == "antModel":
                  ant_model = p.text
                elif p.get("name") == "sectorID":
                  sector_id_val = p.text

            if ant_model and sector_id_val:
              if (
                  ant_model.strip().upper() != "LIBRE"
                  and sector_id_val.strip().upper() != "LIBRE"
              ):
                parts = sector_id_val.split("-")
                for part in parts:
                  part = part.strip()
                  if part.endswith("B") or part.endswith("b"):
                    part = part[:-1]
                  if part:
                    antenna_mapping[part] = ant_model.strip()

        df_xml = pd.DataFrame(list(cells_data.values()))

        all_sectors_set = set(df_xml.get("Sector", []).dropna()).union(
            set(antenna_mapping.keys())
        )
        rows_all = []
        xml_dict_by_sector = {}
        for _, r in df_xml.iterrows():
          xml_dict_by_sector[r["Sector"]] = r.to_dict()

        for sec in all_sectors_set:
          d = xml_dict_by_sector.get(sec, {"Sector": sec})
          if "XML_Antena" not in d or pd.isna(d["XML_Antena"]):
            if sec in antenna_mapping:
              d["XML_Antena"] = antenna_mapping[sec]
          rows_all.append(d)

        df_xml = pd.DataFrame(rows_all)

        # 2. Parsear Plan BSS
        bytes_data = xls_file.read()
        df_xls = None

        try:
          df_xls = pd.read_excel(io.BytesIO(bytes_data))
        except Exception:
          html_content = bytes_data.decode("utf-8", errors="ignore")
          parser = HTMLTableParser()
          parser.feed(html_content)
          if parser.tables:
            table_data = parser.tables[0]
            df_xls = pd.DataFrame(table_data[1:], columns=table_data[0])
          else:
            raise ValueError("No se encontraron tablas HTML en el archivo.")

        df_xls.columns = [str(col).strip().lower() for col in df_xls.columns]

        if "sector" in df_xls.columns and "power" in df_xls.columns:
          if "tipocambio" in df_xls.columns:
            df_xls = df_xls[
                ~df_xls["tipocambio"]
                .astype(str)
                .str.strip()
                .str.lower()
                .eq("eliminar")
            ]

          mimo_col = "mimo" if "mimo" in df_xls.columns else None
          antena_col = "antena" if "antena" in df_xls.columns else None

          expanded_rows = []
          for _, row in df_xls.iterrows():
            sector = str(row["sector"]).strip()
            power_str = str(row["power"]).strip()

            mimo_val = ""
            if mimo_col:
              val = row[mimo_col]
              if pd.notna(val):
                mimo_val = str(val).strip()

            antena_val = ""
            if antena_col:
              val_ant = row[antena_col]
              if pd.notna(val_ant):
                antena_val = str(val_ant).strip()
                if antena_val.upper() == "LIBRE":
                  antena_val = ""

            if "&" in power_str:
              powers = [
                  p.strip().replace(".", "").replace(",", "")
                  for p in power_str.split("&")
              ]
              p1 = "" if powers[0].upper() == "LIBRE" else powers[0]
              p2 = (
                  ""
                  if len(powers) > 1 and powers[1].upper() == "LIBRE"
                  else (powers[1] if len(powers) > 1 else "")
              )

              expanded_rows.append({
                  "Sector": sector,
                  "Excel_pMax": p1,
                  "Excel_dlMimoMode": mimo_val,
                  "Excel_Antena": antena_val,
              })
              if sector.startswith("L"):
                t_sector = "T" + sector[1:]
                expanded_rows.append({
                    "Sector": t_sector,
                    "Excel_pMax": p2,
                    "Excel_dlMimoMode": mimo_val,
                    "Excel_Antena": antena_val,
                })
            else:
              clean_p = (
                  ""
                  if power_str.upper() == "LIBRE"
                  else power_str.replace(".", "").replace(",", "")
              )
              expanded_rows.append({
                  "Sector": sector,
                  "Excel_pMax": clean_p,
                  "Excel_dlMimoMode": mimo_val,
                  "Excel_Antena": antena_val,
              })

          df_plan = pd.DataFrame(expanded_rows).drop_duplicates(
              subset=["Sector"]
          )

          # 3. Cruzar XML y Plan BSS
          merged_df = pd.merge(df_xml, df_plan, on="Sector", how="outer")

          if merged_df.empty:
            st.warning(
                "No se encontraron sectores coincidentes entre el XML y el Plan"
                " BSS."
            )
          else:
            merged_df["XML_pMax"] = (
                merged_df.get("XML_pMax", pd.Series([None] * len(merged_df)))
                .astype(str)
                .str.strip()
            )
            merged_df["XML_pMax"] = merged_df["XML_pMax"].apply(
                lambda x: (
                    ""
                    if x.upper() == "LIBRE"
                    else (x[:-1] if isinstance(x, str) and x.endswith("0") else x)
                )
            )
            merged_df["Excel_pMax"] = (
                merged_df["Excel_pMax"].fillna("").astype(str).str.strip()
            )

            merged_df["XML_Antena"] = (
                merged_df.get("XML_Antena", pd.Series([""] * len(merged_df)))
                .fillna("")
                .astype(str)
                .str.strip()
            )
            merged_df["Excel_Antena"] = (
                merged_df["Excel_Antena"].fillna("").astype(str).str.strip()
            )

            def extract_mimo(val):
              if not val or val == "nan" or str(val).upper() == "LIBRE":
                return ""
              val_str = str(val).lower().strip()
              match = re.search(r"(\d+[xX]\d+)", val_str)
              if match:
                return match.group(1)
              elif "closed loop mimo" in val_str:
                return "2x2"
              return val_str

            merged_df["XML_dlMimoMode"] = (
                merged_df.get("XML_dlMimoMode", pd.Series([""] * len(merged_df)))
                .fillna("")
                .astype(str)
                .str.strip()
            )
            merged_df["Excel_dlMimoMode"] = (
                merged_df["Excel_dlMimoMode"].fillna("").astype(str).str.strip()
            )

            merged_df["XML_Mimo_Clean"] = merged_df["XML_dlMimoMode"].apply(
                extract_mimo
            )
            merged_df["Excel_Mimo_Clean"] = merged_df["Excel_dlMimoMode"].apply(
                extract_mimo
            )

            merged_df["pMax_Igual"] = (
                (merged_df["XML_pMax"] != "")
                & (merged_df["Excel_pMax"] != "")
                & (merged_df["XML_pMax"] == merged_df["Excel_pMax"])
            )
            merged_df["Mimo_Igual"] = (
                (merged_df["XML_Mimo_Clean"] != "")
                & (merged_df["Excel_Mimo_Clean"] != "")
                & (merged_df["XML_Mimo_Clean"] == merged_df["Excel_Mimo_Clean"])
            )
            merged_df["Antena_Igual"] = (
                (merged_df["XML_Antena"] != "")
                & (merged_df["Excel_Antena"] != "")
                & (merged_df["XML_Antena"] == merged_df["Excel_Antena"])
            )

            st.success("¡Comparación completada con éxito!")
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
                    "XML_Antena",
                    "Excel_Antena",
                    "Antena_Igual",
                ]
            ].rename(
                columns={
                    "Sector": "Sector",
                    "XML_pMax": "XML Power",
                    "Excel_pMax": "Excel Power",
                    "pMax_Igual": "pMax Coincide?",
                    "XML_dlMimoMode": "XML MIMO",
                    "Excel_dlMimoMode": "Excel MIMO",
                    "Mimo_Igual": "MIMO Coincide?",
                    "XML_Antena": "XML Antena (antModel)",
                    "Excel_Antena": "Excel Antena",
                    "Antena_Igual": "Antena Coincide?",
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
                    color_matching,
                    subset=[
                        "pMax Coincide?",
                        "MIMO Coincide?",
                        "Antena Coincide?",
                    ],
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
              "El archivo Plan BSS no contiene las columnas requeridas 'sector'"
              " y 'power'."
          )

    except Exception as e:
      st.error(f"Ocurrió un error al procesar los archivos: {e}")
else:
  st.info(
      "Por favor, sube ambos archivos (el XML de configuración y el Plan BSS) y"
      " haz clic en el botón **Comparar**."
  )
