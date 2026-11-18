# PO CSV Builder

A web app for filling an EasyEcom template from emailed PO CSV or XLSX files. It keeps the template's headers, delimiter, line endings, and UTF-8 BOM, and creates one output row per PO row.

## Deploy on Vercel

1. Import this repository into Vercel and use the repository root as the project root.
2. Deploy with the Python runtime. Vercel detects the FastAPI app in `app.py`; no custom entrypoint or `vercel.json` is needed.

Vercel serves the upload and mapping interface at `/`. Uploaded files and the vendor token are processed by the request and are not saved by this app.

## Run locally on Windows

1. Install Python 3.10 or later.
2. Open PowerShell in this folder and install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```
3. Start the app:

   ```powershell
   python -m uvicorn app:app --reload
   ```
4. Open `http://127.0.0.1:8000`, upload the PO file and template CSV, review the suggested mappings, enter the vendor token, and build the output.

The template's first row supplies the output headers and order. Unmapped fields are blank. EAN fields are matched automatically when the source has a uniquely named EAN, EAN Number, EAN No, or EAN Code column; numeric or alphanumeric EAN values are copied as-is, and an empty or missing EAN is left blank. CSV input must be UTF-8 encoded. XLSX input uses the active worksheet.
