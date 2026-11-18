# PO CSV Builder

A small local app for filling an EasyEcom template from emailed PO CSV or XLSX files.

## Run on Windows

1. Install Python 3.10 or later.
2. Open PowerShell in this folder.
3. Install the app dependency:

   ```powershell
   python -m pip install -r requirements.txt
   ```
4. Start the app:

   ```powershell
   python -m streamlit run streamlit_app.py
   ```
5. In the browser, upload the emailed PO file (CSV or XLSX) and template CSV, enter the EasyEcom vendor token, and map the template fields. For an XLSX file, the active worksheet is used. Assign exactly one template field to **Vendor token** and one to **Unit price (10)**.
6. Review the preview and download the completed CSV.

The template's first row supplies the output headers and order. The app creates one output row per PO row, leaves unmapped fields blank, and uses the template's delimiter and line endings. EAN fields are matched automatically when the source has a uniquely named EAN, EAN Number, EAN No, or EAN Code column; numeric or alphanumeric EAN values are copied as-is, and an empty or missing EAN is left blank. CSV input must be UTF-8 encoded.
