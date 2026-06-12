     1|#!/usr/bin/env python3
     2|"""Lightweight embedding server compatible with OpenAI API format.
     3|Serves bge-small-zh-v1.5 on port 11434."""
     4|
     5|import os
     6|import time
     7|import json
     8|import hashlib
     9|from http.server import HTTPServer, BaseHTTPRequestHandler
    10|
    11|os.environ['HF_HUB_OFFLINE2'] = '1'
    12|
    13|print("Loading bge-small-zh-v1.5 model...", flush=True)
    14|from sentence_transformers import SentenceTransformer
    15|model = SentenceTransformer(
    16|    '/mnt/d/bge_model/Xorbits/bge-m3',
    17|    cache_folder=os.path.expanduser('~/.cache/huggingface/hub')
    18|)
    19|print("Model loaded!", flush=True)
    20|
    21|# Warmup
    22|model.encode(['warmup'])
    23|print("Warmup done, starting server on :11434", flush=True)
    24|
    25|# Simple cache
    26|_cache = {}
    27|
    28|class EmbeddingHandler(BaseHTTPRequestHandler):
    29|    def log_message(self, format, *args):
    30|        pass  # Suppress logs
    31|
    32|    def do_GET(self):
    33|        if self.path == '/v1/models':
    34|            self.send_response(200)
    35|            self.send_header('Content-Type', 'application/json')
    36|            self.end_headers()
    37|            resp = {
    38|                "object": "list",
    39|                "data": [{"id": "bge-small-zh-v1.5", "object": "model", "owned_by": "local"}]
    40|            }
    41|            self.wfile.write(json.dumps(resp).encode())
    42|        elif self.path == '/api/tags':
    43|            self.send_response(200)
    44|            self.send_header('Content-Type', 'application/json')
    45|            self.end_headers()
    46|            resp = {"models": [{"name": "bge-small-zh-v1.5"}]}
    47|            self.wfile.write(json.dumps(resp).encode())
    48|        else:
    49|            self.send_response(404)
    50|            self.end_headers()
    51|
    52|    def do_POST(self):
    53|        content_length = int(self.headers.get('Content-Length', 0))
    54|        body = self.rfile.read(content_length)
    55|        
    56|        try:
    57|            data = json.loads(body)
    58|        except:
    59|            self.send_response(400)
    60|            self.end_headers()
    61|            return
    62|
    63|        if self.path == '/v1/embeddings':
    64|            texts = data.get('input', [])
    65|            if isinstance(texts, str):
    66|                texts = [texts]
    67|            
    68|            # Check cache
    69|            results = []
    70|            uncached = []
    71|            uncached_idx = []
    72|            for i, t in enumerate(texts):
    73|                key = hashlib.md5(t.encode()).hexdigest()
    74|                if key in _cache:
    75|                    results.append((_cache[key], i))
    76|                else:
    77|                    uncached.append(t)
    78|                    uncached_idx.append(i)
    79|            
    80|            if uncached:
    81|                embeddings = model.encode(uncached, normalize_embeddings=True)
    82|                for emb, idx in zip(embeddings, uncached_idx):
    83|                    key = hashlib.md5(texts[idx].encode()).hexdigest()
    84|                    _cache[key] = emb.tolist()
    85|                    results.append((emb.tolist(), idx))
    86|            
    87|            results.sort(key=lambda x: x[1])
    88|            
    89|            resp = {
    90|                "object": "list",
    91|                "data": [
    92|                    {"object": "embedding", "embedding": r[0], "index": r[1]}
    93|                    for r in results
    94|                ],
    95|                "model": "bge-small-zh-v1.5",
    96|                "usage": {"prompt_tokens": sum(len(t) for t in texts), "total_tokens": sum(len(t) for t in texts)}
    97|            }
    98|            self.send_response(200)
    99|            self.send_header('Content-Type', 'application/json')
   100|            self.end_headers()
   101|            self.wfile.write(json.dumps(resp).encode())
   102|        else:
   103|            self.send_response(404)
   104|            self.end_headers()
   105|
   106|
   107|server = HTTPServer(('0.0.0.0', 11434), EmbeddingHandler)
   108|print("Server running on port 11434", flush=True)
   109|server.serve_forever()
   110|