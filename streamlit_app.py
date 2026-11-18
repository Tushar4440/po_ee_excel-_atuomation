from pathlib import Path

import streamlit as st

from csv_transform import (
    CsvFormatError,
    read_csv,
    read_source_file,
    suggest_source_column,
    transform_csv,
)


st.set_page_config(page_title="PO File to CSV Builder", page_icon=":material/description:", layout="wide")
st.title("PO File to CSV Builder")
st.caption(
    "Turn an emailed PO CSV or XLSX file into your EasyEcom template. Your files stay in this local app."
)

source_file = st.file_uploader(
    "1. Upload the PO file from email",
    type=["csv", "xlsx"],
    help="CSV and Excel (.xlsx) files are supported. Excel data is read from the active sheet.",
)
template_file = st.file_uploader("2. Upload the EasyEcom template CSV", type=["csv"])

if not source_file or not template_file:
    st.info("Upload the PO file and the EasyEcom template CSV to continue.")
    st.stop()

try:
    source = read_source_file(source_file.getvalue(), source_file.name)
    template = read_csv(template_file.getvalue(), template_file.name)
except CsvFormatError as error:
    st.error(str(error))
    st.stop()

if not source.rows:
    st.error("The PO file has a header row but no order rows.")
    st.stop()

st.write(
    f"**{len(source.rows):,}** PO rows will become **{len(source.rows):,}** output rows. "
    "The template's first row is used as the header; any example rows in the template are replaced."
)

vendor_token = st.text_input(
    "3. EasyEcom vendor token",
    type="password",
    help="Paste the token you copied from EasyEcom. It will be used for every output row.",
)

st.subheader("4. Map template columns")
st.caption(
    "Choose a source column for each template field. Map exactly one field to the vendor token "
    "and one to the fixed unit price of 10. EAN columns are matched automatically when present; "
    "missing or empty EAN values are left blank. Other unmapped fields are also left blank."
)

mapping_options: dict[str, str] = {"blank": "Leave blank"}
for source_index, header in enumerate(source.headers):
    mapping_options[f"source:{source_index}"] = f"Source: {header}"
mapping_options["vendor_token"] = "Vendor token"
mapping_options["unit_price"] = "Unit price (10)"
option_keys = list(mapping_options)
mapping_values: dict[int, str] = {}

left, right = st.columns(2)
for column_index, header in enumerate(template.headers):
    default_key = "blank"
    source_index = suggest_source_column(header, source.headers)
    if source_index is not None:
        default_key = f"source:{source_index}"
    with (left if column_index % 2 == 0 else right):
        mapping_values[column_index] = st.selectbox(
            f"Template field: {header}",
            options=option_keys,
            index=option_keys.index(default_key),
            format_func=mapping_options.get,
            key=f"mapping_{column_index}",
        )

try:
    output_bytes, output_rows = transform_csv(
        source=source,
        template=template,
        mappings=mapping_values,
        vendor_token=vendor_token,
    )
except CsvFormatError as error:
    st.warning(str(error))
else:
    st.subheader("5. Review and download")
    preview = [
        dict(zip(template.headers, row))
        for row in output_rows[:20]
    ]
    st.dataframe(preview, hide_index=True)
    if len(output_rows) > 20:
        st.caption(f"Showing 20 of {len(output_rows):,} output rows.")
    output_name = f"{Path(source_file.name).stem}_updated.csv"
    st.download_button(
        "Download completed CSV",
        data=output_bytes,
        file_name=output_name,
        mime="text/csv",
        type="primary",
    )
