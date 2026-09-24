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


# Función para obtener el número de grupo de sector (ej: 1, L1, T1, M1, S1, R1, G1, X -> '1')
def get_sector_group_num(sector_str):
  sec = str(sector_str).strip().upper()
  if sec in ["X", "1"]:
    return "1"
  if sec in ["Y", "2"]:
    return "2"
  if sec in ["Z", "3"]:
    return "3"
  m = re.search(r"\d+", sec)
  return m.group(0) if m else sec


# Función para normalizar nombres de antenas al comparar
def normalize_antenna(ant_name):
  if not ant_name or pd.isna(ant_name):
    return ""
  ant_str = str(ant_name).strip().upper()
  if ant_str in ["LIBRE", "LIB_SEC"] or ant_str.startswith("LIB"):
    return ""

  ant_str = re.sub(r"_[A-Z0-9]+$", "", ant_str)
  ant_str = re.sub(r"0\d$", "", ant_str)
  return ant_str


col_up1, col_up2 = st.columns(2)
with col_up1:
  xml_file = st.file_uploader("Sube el archivo XML de configuración", type=["xml"])
with col_up2:
  xls_file = st.file_uploader("Sube el archivo Plan BSS", type=["xls", "xlsx"])

# --- CASILLAS PARA ÚLTIMOS 4 DÍGITOS DEL SERIAL POR SECTOR ---
st.subheader("🔢 Últimos 4 dígitos del Serial de Antena por Sector")
st.info(
    "Ingresa los últimos 4 dígitos del serial para cada sector. Estos aplicarán"
    " a sus sectores equivalentes (ej. Sector 1 aplica a 1, L1, T1, M1, S1, R1,"
    " G1, X, etc.)."
)

col_s1, col_s2, col_s3, col_s4 = st.columns(4)
user_serials = {}
with col_s1:
  user_serials["1"] = st.text_input(
      "Sector 1", value="", max_chars=4, placeholder="ej. 6060"
  )
  user_serials["5"] = st.text_input(
      "Sector 5", value="", max_chars=4, placeholder="ej. 1234"
  )
with col_s2:
  user_serials["2"] = st.text_input(
      "Sector 2", value="", max_chars=4, placeholder="ej. 7070"
  )
  user_serials["6"] = st.text_input(
      "Sector 6", value="", max_chars=4, placeholder="ej. 5678"
  )
with col_s3:
  user_serials["3"] = st.text_input(
      "Sector 3", value="", max_chars=4, placeholder="ej. 8080"
  )
  user_serials["7"] = st.text_input(
      "Sector 7", value="", max_chars=4, placeholder="ej. 9012"
  )
with col_s4:
  user_serials["4"] = st.text_input(
      "Sector 4", value="", max_chars=4, placeholder="ej. 9090"
  )
  user_serials["8"] = st.text_input(
      "Sector 8", value="", max_chars=4, placeholder="ej. 3456"
  )

st.divider()

if xml_file is not None and xls_file is not None:
  if st.button("🚀 Comparar", type="primary"):
    try:
      with st.spinner("Procesando y comparando archivos..."):
        # 1. Parsear XML
        tree = ET.parse(xml_file)
        root = tree.getroot()

        cells_data = {}
        antenna_mapping = {}
        antenna_serial_mapping = {}

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
                          and str(param_val).strip().upper()
                          not in ["LIBRE", "LIB_SEC"]
                          and not str(param_val).strip().upper().startswith("LIB")
                      ):
                        if param_name in [
                            "pMax",
                            "maxCarrierPower",
                            "perTrxPower",
                        ]:
                          cells_data[cell_key]["XML_pMax"] = str(param_val)
                        elif param_name == "dlMimoMode":
                          cells_data[cell_key]["XML_dlMimoMode"] = str(
                              param_val
                          )

            ant_model = None
            ant_serial = None
            sector_id_val = None

            for p in elem.findall(".//"):
              if p.tag.endswith("p") and "name" in p.attrib:
                p_name = p.get("name")
                if p_name == "antModel":
                  ant_model = p.text
                elif p_name == "antSerial":
                  ant_serial = p.text
                elif p_name == "sectorID":
                  sector_id_val = p.text

            if ant_model and sector_id_val:
              ant_model_clean = str(ant_model).strip()
              sector_id_clean = str(sector_id_val).strip()
              ant_serial_clean = str(ant_serial).strip() if ant_serial else ""

              if (
                  ant_model_clean.upper() not in ["LIBRE", "LIB_SEC"]
                  and not ant_model_clean.upper().startswith("LIB")
                  and sector_id_clean.upper() not in ["LIBRE", "LIB_SEC"]
                  and not sector_id_clean.upper().startswith("LIB")
              ):
                parts = re.split(r"[-/_]", sector_id_clean)
                for part in parts:
                  part = part.strip()
                  part_upper = part.upper()

                  if (
                      not part
                      or part_upper.endswith("B")
                      or part_upper in ["LIBRE", "LIB_SEC"]
                      or part_upper.startswith("LIB")
                  ):
                    continue

                  antenna_mapping[part] = ant_model_clean
                  if ant_serial_clean:
                    antenna_serial_mapping[part] = ant_serial_clean

        df_xml = pd.DataFrame(list(cells_data.values()))

        all_sectors_set = set(df_xml.get("Sector", []).dropna()).union(
            set(antenna_mapping.keys())
        )
        rows_all = []
        xml_dict_by_sector = {}
        for _, r in df_xml.iterrows():
          xml_dict_by_sector[r["Sector"]] = r.to_dict()

        for sec in all_sectors_set:
          if str(sec).strip().upper().endswith("B"):
            continue
          d = xml_dict_by_sector.get(sec, {"Sector": sec})
          if "XML_Antena" not in d or pd.isna(d["XML_Antena"]):
            if sec in antenna_mapping:
              d["XML_Antena"] = antenna_mapping[sec]
          if "XML_Serial" not in d or pd.isna(d["XML_Serial"]):
            if sec in antenna_serial_mapping:
              d["XML_Serial"] = antenna_serial_mapping[sec]
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
            raw_sector = str(row["sector"]).strip()

            if (
                not raw_sector
                or raw_sector.upper() in ["LIBRE", "LIB_SEC", "NAN"]
                or raw_sector.upper().startswith("LIB")
            ):
              continue

            sector_list = re.split(r"[-/_]", raw_sector)

            for sector in sector_list:
              sector = sector.strip()
              sector_upper = sector.upper()

              if (
                  not sector
                  or sector_upper.endswith("B")
                  or sector_upper in ["LIBRE", "LIB_SEC", "NAN"]
                  or sector_upper.startswith("LIB")
              ):
                continue

              power_val = row["power"]
              power_str = "" if pd.isna(power_val) else str(power_val).strip()

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
                  if (
                      antena_val.upper() in ["LIBRE", "LIB_SEC"]
                      or antena_val.upper().startswith("LIB")
                  ):
                    antena_val = ""

              if "&" in power_str:
                powers = [
                    p.strip().replace(".", "").replace(",", "")
                    for p in power_str.split("&")
                ]
                p1 = (
                    ""
                    if str(powers[0]).upper() in ["LIBRE", "LIB_SEC", "NAN"]
                    else powers[0]
                )
                p2 = (
                    ""
                    if len(powers) > 1
                    and str(powers[1]).upper() in ["LIBRE", "LIB_SEC", "NAN"]
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
                  if not t_sector.endswith("B"):
                    expanded_rows.append({
                        "Sector": t_sector,
                        "Excel_pMax": p2,
                        "Excel_dlMimoMode": mimo_val,
                        "Excel_Antena": antena_val,
                    })
              else:
                clean_p = (
                    ""
                    if power_str.upper() in ["LIBRE", "LIB_SEC", "NAN"]
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
                    if str(x).upper() in ["LIBRE", "LIB_SEC", "NAN"]
                    or str(x).upper().startswith("LIB")
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

            merged_df["XML_Serial"] = (
                merged_df.get("XML_Serial", pd.Series([""] * len(merged_df)))
                .fillna("")
                .astype(str)
                .str.strip()
            )

            merged_df["XML_Serial_Last4"] = merged_df["XML_Serial"].apply(
                lambda s: s[-4:] if len(s) >= 4 else s
            )

            merged_df["Sector_Group"] = merged_df["Sector"].apply(
                get_sector_group_num
            )
            merged_df["Ingresado_Serial_Last4"] = merged_df[
                "Sector_Group"
            ].apply(lambda g: user_serials.get(g, "").strip())

            def extract_mimo(val):
              if (
                  not val
                  or pd.isna(val)
                  or str(val).upper() in ["LIBRE", "LIB_SEC", "NAN"]
                  or str(val).upper().startswith("LIB")
              ):
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

            def process_mimo_row(row):
              sec = str(row["Sector"]).strip().upper()
              is_omitted = sec.startswith("G") or sec in [
                  "X",
                  "Y",
                  "Z",
                  "1",
                  "2",
                  "3",
              ]
              if is_omitted:
                return "", "", "N/A"

              xml_m = str(row["XML_Mimo_Clean"])
              exc_m = str(row["Excel_Mimo_Clean"])
              match_res = xml_m != "" and exc_m != "" and xml_m == exc_m
              return (
                  row["XML_dlMimoMode"],
                  row["Excel_dlMimoMode"],
                  match_res,
              )

            def process_pmax_row(row):
              sec = str(row["Sector"]).strip().upper()
              is_omitted = sec.startswith("G")
              if is_omitted:
                return "N/A"

              xml_p = str(row["XML_pMax"])
              exc_p = str(row["Excel_pMax"])
              return xml_p != "" and exc_p != "" and xml_p == exc_p

            def process_serial_row(row):
              xml_s = str(row["XML_Serial_Last4"]).strip()
              user_s = str(row["Ingresado_Serial_Last4"]).strip()
              if not user_s:
                return "N/A"
              if not xml_s:
                return False
              return xml_s == user_s

            mimo_processed = merged_df.apply(process_mimo_row, axis=1)
            merged_df["XML_dlMimoMode_Disp"] = [x[0] for x in mimo_processed]
            merged_df["Excel_dlMimoMode_Disp"] = [x[1] for x in mimo_processed]
            merged_df["Mimo_Igual"] = [x[2] for x in mimo_processed]

            merged_df["pMax_Igual"] = merged_df.apply(process_pmax_row, axis=1)

            merged_df["Antena_Igual"] = (
                (merged_df["XML_Antena"] != "")
                & (merged_df["Excel_Antena"] != "")
                & (
                    merged_df["XML_Antena"].apply(normalize_antenna)
                    == merged_df["Excel_Antena"].apply(normalize_antenna)
                )
            )

            merged_df["Serial_Igual"] = merged_df.apply(
                process_serial_row, axis=1
            )

            st.session_state["merged_df"] = merged_df
            st.success("¡Comparación completada con éxito!")

        else:
          st.error(
              "El archivo Plan BSS no contiene las columnas requeridas 'sector'"
              " y 'power'."
          )

    except Exception as e:
      st.error(f"Ocurrió un error al procesar los archivos: {e}")

# --- MOSTRAR RESULTADOS VISTA OPTIMIZADA ---
if "merged_df" in st.session_state:
  merged_df = st.session_state["merged_df"]

  st.subheader("📊 Resumen Ejecutivo")
  total_sectores = len(merged_df)
  antena_aciertos = merged_df["Antena_Igual"].sum()

  pmax_valid_df = merged_df[merged_df["pMax_Igual"] != "N/A"]
  total_pmax_val = len(pmax_valid_df)
  pmax_aciertos = (
      (pmax_valid_df["pMax_Igual"] == True).sum() if total_pmax_val > 0 else 0
  )

  mimo_valid_df = merged_df[merged_df["Mimo_Igual"] != "N/A"]
  total_mimo_val = len(mimo_valid_df)
  mimo_aciertos = (
      (mimo_valid_df["Mimo_Igual"] == True).sum() if total_mimo_val > 0 else 0
  )

  serial_valid_df = merged_df[merged_df["Serial_Igual"] != "N/A"]
  total_serial_val = len(serial_valid_df)
  serial_aciertos = (
      (serial_valid_df["Serial_Igual"] == True).sum()
      if total_serial_val > 0
      else 0
  )

  m1, m2, m3, m4, m5 = st.columns(5)
  m1.metric("Total Sectores", total_sectores)
  m2.metric(
      "pMax OK",
      f"{pmax_aciertos} / {total_pmax_val}" if total_pmax_val > 0 else "N/A",
  )
  m3.metric(
      "MIMO OK",
      f"{mimo_aciertos} / {total_mimo_val}" if total_mimo_val > 0 else "N/A",
  )
  m4.metric("Antenas OK", f"{antena_aciertos} / {total_sectores}")
  m5.metric(
      "Seriales OK",
      f"{serial_aciertos} / {total_serial_val}"
      if total_serial_val > 0
      else "N/A",
  )

  st.divider()

  display_table = merged_df[
      [
          "Sector",
          "XML_pMax",
          "Excel_pMax",
          "pMax_Igual",
          "XML_dlMimoMode_Disp",
          "Excel_dlMimoMode_Disp",
          "Mimo_Igual",
          "XML_Antena",
          "Excel_Antena",
          "Antena_Igual",
          "XML_Serial_Last4",
          "Ingresado_Serial_Last4",
          "Serial_Igual",
      ]
  ].rename(
      columns={
          "Sector": "Sector",
          "XML_pMax": "XML Pwr",
          "Excel_pMax": "Excel Pwr",
          "pMax_Igual": "Pwr OK?",
          "XML_dlMimoMode_Disp": "XML MIMO",
          "Excel_dlMimoMode_Disp": "Excel MIMO",
          "Mimo_Igual": "MIMO OK?",
          "XML_Antena": "XML Antena",
          "Excel_Antena": "Excel Antena",
          "Antena_Igual": "Antena OK?",
          "XML_Serial_Last4": "XML 4Dig",
          "Ingresado_Serial_Last4": "Digitado",
          "Serial_Igual": "Serial OK?",
      }
  )

  # --- FILTROS INTERACTIVOS ---
  filtro_opcion = st.radio(
      "Filtrar resultados:",
      [
          "Mostrar todos",
          "Solo con errores (discrepancias)",
          "Solo coincidencias perfectas",
      ],
      horizontal=True,
  )

  if filtro_opcion == "Solo con errores (discrepancias)":
    display_table = display_table[
        (display_table["Pwr OK?"] == False)
        | (display_table["Antena OK?"] == False)
        | (display_table["MIMO OK?"] == False)
        | (display_table["Serial OK?"] == False)
    ]
  elif filtro_opcion == "Solo coincidencias perfectas":
    display_table = display_table[
        (
            (display_table["Pwr OK?"] == True)
            | (display_table["Pwr OK?"] == "N/A")
        )
        & (display_table["Antena OK?"] == True)
        & (
            (display_table["MIMO OK?"] == True)
            | (display_table["MIMO OK?"] == "N/A")
        )
        & (
            (display_table["Serial OK?"] == True)
            | (display_table["Serial OK?"] == "N/A")
        )
    ]


  def color_matching(col):
    colors = []
    for val in col:
      if val is True:
        colors.append("background-color: #d4edda; color: #155724")
      elif val is False:
        colors.append("background-color: #f8d7da; color: #721c24")
      else:
        colors.append("")
    return colors


  # --- ORGANIZACIÓN DE TABLAS POR PESTAÑAS ---
  st.subheader("🔍 Resultados Detallados por Categoría")
  tab_pwr, tab_ant, tab_full = st.tabs(
      ["⚡ Potencia & MIMO", "📡 Antena & Seriales", "📋 Vista Completa"]
  )

  with tab_pwr:
    cols_pwr = [
        "Sector",
        "XML Pwr",
        "Excel Pwr",
        "Pwr OK?",
        "XML MIMO",
        "Excel MIMO",
        "MIMO OK?",
    ]
    df_pwr = display_table[cols_pwr]
    st.dataframe(
        df_pwr.style.apply(
            color_matching, subset=["Pwr OK?", "MIMO OK?"]
        ),
        use_container_width=True,
        hide_index=True,
    )

  with tab_ant:
    cols_ant = [
        "Sector",
        "XML Antena",
        "Excel Antena",
        "Antena OK?",
        "XML 4Dig",
        "Digitado",
        "Serial OK?",
    ]
    df_ant = display_table[cols_ant]
    st.dataframe(
        df_ant.style.apply(
            color_matching, subset=["Antena OK?", "Serial OK?"]
        ),
        use_container_width=True,
        hide_index=True,
    )

  with tab_full:
    st.dataframe(
        display_table.style.apply(
            color_matching,
            subset=["Pwr OK?", "MIMO OK?", "Antena OK?", "Serial OK?"],
        ),
        use_container_width=True,
        hide_index=True,
    )

  st.divider()
  st.subheader("📥 Descargar Reporte")
  csv_data = display_table.to_csv(index=False).encode("utf-8")
  st.download_button(
      label="📥 Descargar Reporte Filtrado en CSV",
      data=csv_data,
      file_name="comparacion_xml_planbss.csv",
      mime="text/csv",
  )

else:
  st.info(
      "Por favor, sube ambos archivos (el XML de configuración y el Plan BSS) y"
      " haz clic en el botón **Comparar**."
  )
