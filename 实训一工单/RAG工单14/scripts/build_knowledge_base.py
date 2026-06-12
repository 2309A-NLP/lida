#!/usr/bin/env python3
"""
RAGFlow 知识库构建脚本
用法: python build_knowledge_base.py [--api-key YOUR_API_KEY]
"""

import os
import sys
import json
import requests
import argparse
from pathlib import Path

# 配置
RAGFLOW_URL = "http://localhost:9380"
DOCUMENTS_DIR = "/mnt/d/RAG工单14/documents"
KNOWLEDGE_BASE_NAME = "IMDR工业文档"
DOCUMENT_NAME = "CN100342976C.pdf"

# 默认分块参数
DEFAULT_PARSER_CONFIG = {
    "chunk_token_num": 512,
    "delimiter": "\n!?。；！？",
    "layout_recognize": "DeepDOC",
    "html4excel": False,
    "raptor": False,
    "graphrag": False,
    "table_context_size": 8,
    "image_context_size": 3,
    "auto_keywords": False,
    "auto_questions": False
}


class RAGFlowClient:
    def __init__(self, base_url, api_key=None):
        self.base_url = base_url.rstrip('/')
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    def _request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def create_knowledge_base(self, name, description=""):
        """创建知识库"""
        data = {
            "name": name,
            "description": description,
            "permission": "me",
            "chunk_method": "naive",
            "parser_config": DEFAULT_PARSER_CONFIG
        }
        return self._request("POST", "/api/v1/knowledge_base", json=data)
    
    def list_knowledge_bases(self):
        """列出所有知识库"""
        return self._request("GET", "/api/v1/knowledge_base")
    
    def upload_document(self, kb_id, file_path):
        """上传文档到知识库"""
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
            response = requests.post(
                f"{self.base_url}/api/v1/knowledge_base/{kb_id}/document",
                headers={"Authorization": self.headers.get("Authorization", "")},
                files=files
            )
            response.raise_for_status()
            return response.json()
    
    def parse_document(self, kb_id, doc_id):
        """触发文档解析"""
        return self._request("POST", f"/api/v1/knowledge_base/{kb_id}/document/{doc_id}/parse")
    
    def get_document_status(self, kb_id, doc_id):
        """获取文档解析状态"""
        return self._request("GET", f"/api/v1/knowledge_base/{kb_id}/document/{doc_id}")
    
    def retrieval(self, kb_id, question, top_k=10):
        """检索"""
        data = {
            "question": question,
            "kb_ids": [kb_id],
            "top_k": top_k
        }
        return self._request("POST", "/api/v1/retrieval", json=data)


def main():
    parser = argparse.ArgumentParser(description="构建RAGFlow知识库")
    parser.add_argument("--api-key", help="RAGFlow API Key")
    parser.add_argument("--url", default=RAGFLOW_URL, help="RAGFlow URL")
    parser.add_argument("--upload-all", action="store_true", help="上传所有1700个PDF")
    args = parser.parse_args()
    
    client = RAGFlowClient(args.url, args.api_key)
    
    print("=== 构建 RAGFlow 知识库 ===")
    print(f"RAGFlow URL: {args.url}")
    print()
    
    # 1. 创建知识库
    print("[1/4] 创建知识库...")
    try:
        result = client.create_knowledge_base(
            KNOWLEDGE_BASE_NAME,
            "IMDR工业制造领域多模态数据集"
        )
        kb_id = result.get("data", {}).get("id")
        print(f"  知识库创建成功: {KNOWLEDGE_BASE_NAME} (ID: {kb_id})")
    except Exception as e:
        print(f"  [ERROR] 创建知识库失败: {e}")
        # 尝试获取已存在的知识库
        try:
            kbs = client.list_knowledge_bases()
            for kb in kbs.get("data", []):
                if kb["name"] == KNOWLEDGE_BASE_NAME:
                    kb_id = kb["id"]
                    print(f"  使用已存在的知识库: {kb_id}")
                    break
            else:
                print("  [ERROR] 未找到知识库")
                sys.exit(1)
        except Exception as e2:
            print(f"  [ERROR] 获取知识库列表失败: {e2}")
            sys.exit(1)
    
    # 2. 上传测试文档
    print("[2/4] 上传测试文档...")
    test_doc_path = os.path.join(DOCUMENTS_DIR, DOCUMENT_NAME)
    if os.path.exists(test_doc_path):
        try:
            result = client.upload_document(kb_id, test_doc_path)
            doc_id = result.get("data", {}).get("id")
            print(f"  文档上传成功: {DOCUMENT_NAME} (ID: {doc_id})")
        except Exception as e:
            print(f"  [ERROR] 上传文档失败: {e}")
            sys.exit(1)
    else:
        print(f"  [ERROR] 文档不存在: {test_doc_path}")
        sys.exit(1)
    
    # 3. 触发解析
    print("[3/4] 触发文档解析...")
    try:
        result = client.parse_document(kb_id, doc_id)
        print(f"  解析已触发")
    except Exception as e:
        print(f"  [ERROR] 触发解析失败: {e}")
    
    # 4. 等待解析完成
    print("[4/4] 等待解析完成...")
    import time
    while True:
        try:
            status = client.get_document_status(kb_id, doc_id)
            doc_status = status.get("data", {}).get("status")
            if doc_status == "1":  # 解析完成
                print("  解析完成!")
                break
            elif doc_status == "0":  # 解析中
                print("  解析中...")
                time.sleep(10)
            else:
                print(f"  状态: {doc_status}")
                time.sleep(10)
        except Exception as e:
            print(f"  [ERROR] 获取状态失败: {e}")
            time.sleep(10)
    
    # 5. 上传所有文档（可选）
    if args.upload_all:
        print("\n=== 上传所有文档 ===")
        pdf_files = list(Path(DOCUMENTS_DIR).glob("*.pdf"))
        print(f"共 {len(pdf_files)} 个PDF文件")
        
        for i, pdf_file in enumerate(pdf_files, 1):
            if pdf_file.name == DOCUMENT_NAME:
                continue  # 跳过已上传的
            try:
                client.upload_document(kb_id, str(pdf_file))
                if i % 100 == 0:
                    print(f"  已上传 {i}/{len(pdf_files)}")
            except Exception as e:
                print(f"  [ERROR] 上传 {pdf_file.name} 失败: {e}")
    
    print("\n=== 构建完成 ===")
    print(f"知识库ID: {kb_id}")
    print(f"测试文档ID: {doc_id}")
    print("\n下一步: 运行 python scripts/test_questions.py 测试问题")


if __name__ == "__main__":
    main()
