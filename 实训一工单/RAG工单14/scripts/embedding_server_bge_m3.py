#!/usr/bin/env python3
"""Embedding server using bge-m3, reporting as bge-small-zh-v1.5 for compatibility."""

import os
import json
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler

print("Loading bge-m3 model...", flush=True)
from sentence_transformers import SentenceTransformer
model = SentenceTransformer(
    '/mnt/d/bge_model/Xorbits/bge-m3',
    device='cpu'
)
print("Model loaded!", flush=True)

# Warmup
model.encode(['warmup'])
print("Warmup done, starting server on :11434", flush=True)

_cache = {}

class EmbeddingHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == '/v1/models':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            resp = {
                "object": "list",
                "data": [{"id": "bge-m3", "object": "model", "owned_by": "local"}]
            }
            self.wfile.write(json.dumps(resp).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body)
        except:
            self.send_response(400)
            self.end_headers()
            return

        if self.path == '/v1/embeddings':
            texts = data.get('input', [])
            if isinstance(texts, str):
                texts = [texts]
            
            results = []
            uncached = []
            uncached_idx = []
            for i, t in enumerate(texts):
                key = hashlib.md5(t.encode()).hexdigest()
                if key in _cache:
                    results.append((_cache[key], i))
                else:
                    uncached.append(t)
                    uncached_idx.append(i)
            
            if uncached:
                embeddings = model.encode(uncached, normalize_embeddings=True)
                for emb, idx in zip(embeddings, uncached_idx):
                    key = hashlib.md5(texts[idx].encode()).hexdigest()
                    _cache[key] = emb.tolist()
                    results.append((emb.tolist(), idx))
            
            results.sort(key=lambda x: x[1])
            
            resp = {
                "object": "list",
                "data": [
                    {"object": "embedding", "embedding": r[0], "index": r[1]}
                    for r in results
                ],
                "model": "bge-m3",
                "usage": {"prompt_tokens": sum(len(t) for t in texts), "total_tokens": sum(len(t) for t in texts)}
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())
        else:
            self.send_response(404)
            self.end_headers()

server = HTTPServer(('0.0.0.0', 11434), EmbeddingHandler)
print("Server running on port 11434", flush=True)
server.serve_forever()
