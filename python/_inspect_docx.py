import sys, zipfile, re, collections

path = sys.argv[1]
with zipfile.ZipFile(path) as z:
    x = z.read("word/document.xml").decode("utf-8")

szs = re.findall(r'<w:sz w:val="(\d+)"', x)
print("font sizes (half-pt) histogram:", collections.Counter(szs))
# Convert each unique to pt
unique_pt = sorted({int(v) / 2.0 for v in szs})
print("unique font pt:", unique_pt)