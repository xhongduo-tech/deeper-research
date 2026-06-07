# Conversion Matrix

| From | To | Primary Path | QA |
|------|----|--------------|----|
| Markdown | DOCX | python-docx / Pandoc fallback | open and inspect headings, tables, images |
| Markdown | PPTX | SlideSpec + python-pptx | render to PDF/image |
| Markdown | XLSX | openpyxl / XlsxWriter | open workbook and count formulas/charts |
| DOCX | PDF | LibreOffice headless | render pages via PyMuPDF/Poppler |
| PPTX | PDF/images | LibreOffice headless | check blank pages, overflow, contrast |
| XLSX | PDF | LibreOffice headless | inspect sheet renderability |

All paths must run offline in intranet deployments.
