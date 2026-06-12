import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

print("加载 bge-reranker-base 模型...", flush=True)
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

model_path = "/mnt/d/重排序模型/bge-reranker-base"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)
model.eval()
print("模型加载完成！", flush=True)

# 预热
with torch.no_grad():
    inputs = tokenizer("test", "test", return_tensors="pt", padding=True, truncation=True, max_length=512)
    model(**inputs)
print("预热完成，启动服务...", flush=True)


class RerankerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except:
            self.send_response(400)
            self.end_headers()
            return

        # 支持多种路径格式
        query = data.get('query', '')
        documents = data.get('documents', data.get('docs', []))
        top_n = data.get('top_n', len(documents))

        if not query or not documents:
            self.send_response(400)
            self.end_headers()
            return

        # 计算相关性分数
        scores = []
        with torch.no_grad():
            for doc in documents:
                doc_text = doc if isinstance(doc, str) else doc.get('content', str(doc))
                inputs = tokenizer(query, doc_text, return_tensors="pt", padding=True, truncation=True, max_length=512)
                outputs = model(**inputs)
                score = outputs.logits.item()
                scores.append(score)

        # 排序
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_n]

        results = []
        for idx, score in ranked:
            results.append({
                "index": idx,
                "relevance_score": score,
                "document": documents[idx] if idx < len(documents) else ""
            })

        resp = {"results": results}

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode())


server = HTTPServer(('0.0.0.0', 11435), RerankerHandler)
print("Reranker 服务运行在端口 11435", flush=True)
server.serve_forever()
