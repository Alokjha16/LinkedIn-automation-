import fitz
from pathlib import Path

for pdf in sorted(Path("outputs/resumes").glob("custom_resume_*.pdf"))[:3]:
    doc = fitz.open(pdf)
    text = ""
    for page in doc:
        text += page.get_text()

    print("\n" + "=" * 80)
    print(pdf.name)
    print("=" * 80)

    start = text.find("SUMMARY")
    end = text.find("SKILLS")

    if start != -1 and end != -1:
        print(text[start:end].strip())
    else:
        print(text[:1200])