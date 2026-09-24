"""Rebuild raw_data/phase_of_disease_evidence.csv from public pages.

Pages are read into memory and parsed; nothing is saved except the extracted CSV.
Run from anywhere: python utils/fetch_phase_of_disease_evidence.py
"""

import html
import pathlib
import re
import sys
import urllib.request

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from cell_line_utils import normalize_name  # noqa: E402

RETRIEVED = "2026-09-23"
BASE = "https://www.cccells.org/tables/"
CATALOG_PAGES = [
    BASE + "cellreq-tbl_braintumor.php",
    BASE + "cellreq-tbl_eft_ewings.php",
    BASE + "cellreq-tbl_ped_sarcomas.php",
    BASE + "Retinoblastoma.php",
    BASE + "Wilms.php",
]
PPTP_XML = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id=3005554&rettype=xml&retmode=xml"
PPTP_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC3005554/"
EFT_PANEL_URL = "https://www.cccells.org/dl/COG_EFT_Cell_Line_Panel.pdf"
REPOSITORY_CODES = ("Dx", "PD", "PD-BMT", "PD-PM", "P-EBR")
PPTP_CODES = {"DX": "Dx", "Post-Tx": "PD", "Post-BMT": "PD-BMT"}


def fetch(url):
    """Download a page and return its text (with a browser user agent, since some sites refuse the default one)."""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", "ignore")


def clean(cell):
    """Plain text of an HTML table cell: strip tags and entities, collapse whitespace, drop a leading ">" marker."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", cell))).strip().lstrip("> ").strip()


workbook = pd.ExcelFile(ROOT / "raw_data" / "Rambutan_Atlasv2_April2026.xlsx")
names = workbook.parse("Atlas conditions", header=None)[0].dropna().astype(str)
atlas_name = {}
for name in names[names != "Cell Line"]:
    atlas_name.setdefault(normalize_name(name), name)

records = []

# Repository catalog tables: a line's row reads name, PDX, phase, ...
for url in CATALOG_PAGES:
    for row in re.split(r"(?i)<tr", fetch(url))[1:]:
        cells = [clean(c) for c in re.split(r"(?i)</t[dh]>", re.split(r"(?i)</tr", row)[0])]
        for i, cell in enumerate(cells):
            key = normalize_name(cell.strip("*"))
            if key in atlas_name and i + 2 < len(cells):
                if cells[i + 2] in REPOSITORY_CODES:
                    records.append({"cell_line": atlas_name[key], "evidence_source": "Repository catalog table",
                                    "value_as_published": cells[i + 2], "phase_of_disease": cells[i + 2], "url": url})
                break

# PPTP paper (Kang et al. 2011), Table 1. Footnotes: * relapse after chemotherapy, ** relapse after myeloablative
# chemotherapy with bone marrow transplantation, section sign = at diagnosis before treatment
table = re.findall(r"<table-wrap.*?</table-wrap>", fetch(PPTP_XML), re.S)[0]
for row in re.findall(r"<tr.*?</tr>", table, re.S):
    cells = [clean(c) for c in re.findall(r"<t[dh].*?</t[dh]>", row, re.S)]
    key = normalize_name(cells[0]) if cells else None
    code = next((c for c in cells[1:] if re.match(r"^(DX|Post-Tx|Post-BMT)", c)), None)
    if key in atlas_name and code:
        records.append({"cell_line": atlas_name[key], "evidence_source": "PPTP paper (Kang 2011) Table 1", "value_as_published": code,
                        "phase_of_disease": PPTP_CODES[re.match(r"^(DX|Post-Tx|Post-BMT)", code).group(1)], "url": PPTP_URL})

# Repository Ewing panel PDF (dl/COG_EFT_Cell_Line_Panel.pdf): the SK-N-MC row reads "Post Chemo" (vincristine,
# cyclophosphamide, doxorubicin, actinomycin, 1968-1971). Read by hand; the layout is not machine-parseable.
records.append({"cell_line": atlas_name["SKNMC"], "evidence_source": "Repository Ewing panel PDF", "value_as_published": "Post Chemo",
                "phase_of_disease": "PD", "url": EFT_PANEL_URL})

evidence = pd.DataFrame(records)
evidence["retrieved"] = RETRIEVED
evidence = evidence.sort_values(["cell_line", "evidence_source"]).reset_index(drop=True)
assert not evidence.duplicated(["cell_line", "evidence_source"]).any()
evidence.to_csv(ROOT / "raw_data" / "phase_of_disease_evidence.csv", index=False)
print(evidence.shape, "rows |", evidence["cell_line"].nunique(), "lines")
