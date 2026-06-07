#!python3
"""Test ONNX model directly"""
import numpy as np
import onnxruntime as ort
import json

model_path = '/home/lida/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx/model.onnx'
tokenizer_path = '/home/lida/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx/tokenizer.json'

print(f'Model exists: {__import__("os").path.exists(model_path)}')
print(f'Tokenizer exists: {__import__("os").path.exists(tokenizer_path)}')

# Try loading tokenizer.json directly
with open(tokenizer_path) as f:
    tok_data = json.load(f)
print(f'Tokenizer keys: {list(tok_data.keys())}')
