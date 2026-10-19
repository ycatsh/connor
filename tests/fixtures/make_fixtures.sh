#!/usr/bin/env sh
set -eu

here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export TZ=UTC

convert() {
    soffice "-env:UserInstallation=file://$work/profile" --headless \
        --convert-to "$1" --outdir "$here" "$2" >/dev/null 2>&1
}

cd "$here/src"
convert "docx:MS Word 2007 XML" lab_report.html
convert odt:writer8 lab_report.html
convert "doc:MS Word 97" lab_report.html
convert "rtf:Rich Text Format" lab_report.html
convert pdf:writer_web_pdf_Export lab_report.html
convert pdf:writer_web_pdf_Export blank.html
convert xlsx grades.csv
convert ods grades.csv
convert "xls:MS Excel 97" grades.csv
pandoc slides.md -o "$here/slides.pptx"
convert odp "$here/slides.pptx"
pandoc novel.md -o "$here/novel.epub"

python3 -I - "$here" "$(id -un)" "$(hostname)" "$HOME" <<'PY'
import sys
import zipfile
from pathlib import Path

folder, *needles = sys.argv[1:]
found = []
for path in sorted(Path(folder).glob("*.*")):
    blobs = [path.read_bytes()]
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            blobs += [archive.read(name) for name in archive.namelist()]
    for needle in needles:
        for encoding in ("utf-8", "utf-16-le", "utf-16-be"):
            if any(needle.lower().encode(encoding) in blob.lower() for blob in blobs):
                found.append(f"{path.name}: {encoding}")
if found:
    print("personal data found in fixtures:", *found, sep="\n  ")
    sys.exit(1)
print("fixtures written, no personal data found")
PY
