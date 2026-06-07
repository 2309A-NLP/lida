import fitz
doc = fitz.open('/mnt/d/RAG工单7/2022-03-31__国泰君安证券股份有限公司__601211__国泰君安__2021年__年度报告.pdf')
print(f'Total pages: {len(doc)}')
for i in range(min(8, len(doc))):
    text = doc[i].get_text().strip()
    print(f'\n--- Page {i+1} ---')
    print(text[:1000])
doc.close()
