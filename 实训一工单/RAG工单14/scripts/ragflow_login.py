#!/usr/bin/env python3
"""RAGFlow用户创建和登录脚本"""
import sys
import os
import base64
import requests
import json

# 导入RAGFlow的加密模块
sys.path.insert(0, '/mnt/d/ragflow')

def crypt_password(password):
    """使用RAGFlow的RSA加密方式加密密码"""
    from pathlib import Path
    from Cryptodome.PublicKey import RSA
    from Cryptodome.Cipher import PKCS1_v1_5 as Cipher_pkcs1_v1_5
    
    file_path = os.path.join('/mnt/d/ragflow', 'conf', 'public.pem')
    rsa_key = RSA.importKey(Path(file_path).read_text(), "Welcome")
    cipher = Cipher_pkcs1_v1_5.new(rsa_key)
    password_base64 = base64.b64encode(password.encode('utf-8')).decode('utf-8')
    encrypted_password = cipher.encrypt(password_base64.encode())
    return base64.b64encode(encrypted_password).decode('utf-8')

def login(email, password):
    """登录RAGFlow"""
    encrypted = crypt_password(password)
    url = 'http://localhost:9380/api/v1/auth/login'
    data = {
        'email': email,
        'password': encrypted
    }
    response = requests.post(url, json=data)
    return response.json()

def get_api_key(token):
    """获取API Key"""
    url = 'http://localhost:9380/api/v1/users/me'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)
    return response.json()

if __name__ == '__main__':
    # 尝试用默认管理员账号登录
    email = 'admin@ragflow.io'
    password = 'admin'
    
    print(f"尝试登录: {email}")
    result = login(email, password)
    print(f"登录结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get('code') == 0:
        token = result.get('data', {}).get('access_token')
        if token:
            print(f"\nToken: {token}")
            
            # 获取用户信息
            user_info = get_api_key(token)
            print(f"\n用户信息: {json.dumps(user_info, indent=2, ensure_ascii=False)}")
