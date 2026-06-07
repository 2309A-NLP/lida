#!python3
"""
工单编号：人工智能NLP-RAG-图像内容解析及检索优化
构建多模态图像语义索引（本地视觉特征 + OCR + 页面上下文融合）
无需下载外部模型，使用 Pillow + numpy + scipy 实现视觉特征提取
"""
import os, sys, json, re, time, io, hashlib, math
from pathlib import Path
from PIL import Image, ImageFilter, ImageOps
import numpy as np
from scipy import ndimage
import fitz

BASE_DIR = '/mnt/d/RAG工单/RAG工单4'
CACHE_DIR = os.path.join(BASE_DIR, 'image_cache')
IMAGE_INDEX_PATH = os.path.join(BASE_DIR, 'image_descriptions.json')
VISUAL_INDEX_PATH = os.path.join(BASE_DIR, 'visual_index.json')

page_text_cache = {}

def get_page_text(pdf_path, page_num):
    key = (os.path.basename(pdf_path), page_num)
    if key in page_text_cache:
        return page_text_cache[key]
    try:
        doc = fitz.open(pdf_path)
        text = doc[page_num].get_text().strip() if page_num < len(doc) else ''
        doc.close()
        page_text_cache[key] = text
        return text
    except:
        return ''

def extract_visual_features(pil_img):
    """提取多模态视觉特征向量（512维）"""
    features = []
    
    # 1. 颜色特征：HSV 直方图（60维：30Hue × 15Saturation × 15Value bins）
    if pil_img.mode != 'RGB':
        pil_img = pil_img.convert('RGB')
    hsv = pil_img.convert('HSV')
    hsv_np = np.array(hsv)
    h_hist = np.histogram(hsv_np[:,:,0], bins=30, range=(0, 180))[0].astype(float)
    s_hist = np.histogram(hsv_np[:,:,1], bins=15, range=(0, 256))[0].astype(float)
    v_hist = np.histogram(hsv_np[:,:,2], bins=15, range=(0, 256))[0].astype(float)
    h_hist = h_hist / (h_hist.sum() + 1e-8)
    s_hist = s_hist / (s_hist.sum() + 1e-8)
    v_hist = v_hist / (v_hist.sum() + 1e-8)
    features.extend(h_hist.tolist())
    features.extend(s_hist.tolist())
    features.extend(v_hist.tolist())
    
    # 2. 纹理特征（60维）
    gray_np = np.array(pil_img.convert('L'), dtype=float)
    sx = ndimage.sobel(gray_np, axis=1)
    sy = ndimage.sobel(gray_np, axis=0)
    edge_mag = np.sqrt(sx**2 + sy**2)
    edge_dir = np.arctan2(sy, sx + 1e-8)
    edge_hist = np.histogram(edge_dir.flatten(), bins=36, range=(-np.pi, np.pi), weights=edge_mag.flatten())[0]
    edge_hist = edge_hist / (edge_hist.sum() + 1e-8)
    features.extend(edge_hist.tolist())
    mag_hist = np.histogram(edge_mag.flatten(), bins=24, range=(0, 255))[0].astype(float)
    mag_hist = mag_hist / (mag_hist.sum() + 1e-8)
    features.extend(mag_hist.tolist())
    
    # 3. 图像统计特征（24维）
    img_array = np.array(pil_img)
    if img_array.ndim == 2:
        img_array = np.stack([img_array] * 3, axis=-1)
    for channel in range(3):
        ch = img_array[:,:,channel].astype(float).flatten()
        features.append(float(np.mean(ch)))
        features.append(float(np.std(ch)))
        features.append(float(np.percentile(ch, 25)))
        features.append(float(np.percentile(ch, 75)))
        features.append(float(np.percentile(ch, 50)))
        features.append(float(np.mean(ch**2)))
        features.append(float(np.sqrt(np.mean(ch**4))))
        features.append(float(np.sum(np.abs(np.diff(ch.reshape(-1))))))
    
    # 4. 形状特征（9维）
    w, h = pil_img.size
    area = w * h
    features.append(w / max(h, 1))
    features.append(math.log10(max(area, 1)))
    binary = (gray_np > np.mean(gray_np)).astype(np.uint8)
    labeled, num_features = ndimage.label(binary)
    features.append(float(num_features))
    if num_features > 0:
        sizes = np.bincount(labeled.flatten())[1:]
        features.append(float(np.mean(sizes)))
        features.append(float(np.std(sizes)))
        features.append(float(np.max(sizes)) / max(area, 1))
    else:
        features.extend([0.0, 0.0, 0.0, 0.0])
    h_edge = np.abs(sx) > np.percentile(np.abs(sx), 90)
    row_edge_density = np.mean(h_edge, axis=1)
    horiz_line_count = np.sum(row_edge_density > 0.3)
    features.append(float(horiz_line_count))
    v_edge = np.abs(sy) > np.percentile(np.abs(sy), 90)
    col_edge_density = np.mean(v_edge, axis=0)
    vert_line_count = np.sum(col_edge_density > 0.3)
    features.append(float(vert_line_count))
    features.append(float(horiz_line_count) / (vert_line_count + 1))
    
    # 5. 空间分布特征（32维）
    cells_x, cells_y = 4, 4
    cell_h, cell_w = h // cells_y, w // cells_x
    for cy in range(cells_y):
        for cx in range(cells_x):
            y1 = cy * cell_h
            y2 = (cy + 1) * cell_h if cy < cells_y - 1 else h
            x1 = cx * cell_w
            x2 = (cx + 1) * cell_w if cx < cells_x - 1 else w
            cell = gray_np[y1:y2, x1:x2]
            features.append(float(np.mean(cell)))
            features.append(float(np.std(cell)))
    
    # 归一化到单位向量
    features = np.array(features, dtype=np.float32)
    norm = np.linalg.norm(features)
    if norm > 0:
        features = features / norm
    # 填充到512维
    if len(features) < 512:
        features = np.pad(features, (0, 512 - len(features)), 'constant')
    return features[:512]

def classify_image_type(pil_img, ocr_text, page_text):
    """使用视觉特征+OCR文本分类图像类型"""
    scores = {'chart': 0.0, 'table': 0.0, 'org_chart': 0.0, 'photo': 0.0, 'diagram': 0.0, 'text_page': 0.0}
    
    if pil_img.mode != 'RGB':
        pil_img_rgb = pil_img.convert('RGB')
    else:
        pil_img_rgb = pil_img
    
    gray = np.array(pil_img.convert('L'), dtype=float)
    w, h = pil_img.size
    area = w * h
    
    sx = ndimage.sobel(gray, axis=1)
    sy = ndimage.sobel(gray, axis=0)
    edge_mag = np.sqrt(sx**2 + sy**2)
    edge_density = np.mean(edge_mag > np.percentile(edge_mag, 85))
    h_edge_strength = np.mean(np.abs(sx))
    v_edge_strength = np.mean(np.abs(sy))
    hv_ratio = h_edge_strength / (v_edge_strength + 1e-8)
    
    img_np = np.array(pil_img_rgb)
    color_std = np.mean([np.std(img_np[:,:,c]) for c in range(3)])
    ocr_len = len(ocr_text.strip())
    
    if edge_density > 0.15 and edge_density < 0.4 and hv_ratio > 0.8 and hv_ratio < 1.8:
        scores['chart'] += 0.6
        if ocr_len > 20 and ocr_len < 500:
            scores['chart'] += 0.3
        if color_std > 30:
            scores['chart'] += 0.2
    
    if hv_ratio > 1.5 and edge_density > 0.2:
        scores['table'] += 0.5
        if ocr_len > 50:
            scores['table'] += 0.3
        row_edges = np.mean(np.abs(sx) > np.percentile(np.abs(sx), 90), axis=1)
        if np.std(row_edges) < 0.2:
            scores['table'] += 0.2
    
    if edge_density > 0.1 and edge_density < 0.3 and hv_ratio > 0.6 and hv_ratio < 1.5:
        if any(kw in ocr_text for kw in ['部', '公司', '总', '经理', '主任', '科长', '中心']):
            scores['org_chart'] += 0.7
        if '组织' in page_text or '结构' in page_text or '架构' in page_text:
            scores['org_chart'] += 0.3
    
    if color_std > 50:
        scores['photo'] += 0.5
        if edge_density > 0.3:
            scores['photo'] += 0.3
        if ocr_len < 50:
            scores['photo'] += 0.2
    
    if edge_density > 0.1 and edge_density < 0.35:
        scores['diagram'] += 0.4
        if any(kw in ocr_text for kw in ['→', '->', '流程', '步骤', '开始', '结束', '判断']):
            scores['diagram'] += 0.4
        if '流程' in page_text or '图' in page_text:
            scores['diagram'] += 0.2
    
    if ocr_len > 200:
        scores['text_page'] += 0.6
        if color_std < 30:
            scores['text_page'] += 0.3
        if edge_density < 0.15:
            scores['text_page'] += 0.2
    
    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    type_labels = {
        'chart': 'chart/graph/figure', 'table': 'table/data grid',
        'org_chart': 'organization chart/hierarchy diagram',
        'photo': 'photograph/image', 'diagram': 'diagram/flowchart',
        'text_page': 'text document page'
    }
    return best_type, best_score, scores, type_labels[best_type]

def generate_rich_description(pil_img, ocr_text, page_context, img_type, img_score, visual_feats):
    """生成融合多模态信息的图像语义描述"""
    w, h = pil_img.size
    parts = []
    parts.append(f'[图像尺寸] {w}x{h}像素')
    parts.append(f'[图像类型] {img_type}（置信度:{img_score:.2f}）')
    
    if ocr_text.strip():
        parts.append(f'[OCR提取文本]\n{ocr_text[:1500]}')
    else:
        parts.append('[OCR提取文本] 未提取到文本内容，图像可能以图形/照片为主')
    
    gray = np.array(pil_img.convert('L'), dtype=float)
    sx = ndimage.sobel(gray, axis=1)
    sy = ndimage.sobel(gray, axis=0)
    edge_mag = np.sqrt(sx**2 + sy**2)
    edge_density = np.mean(edge_mag > np.percentile(edge_mag, 85))
    
    if pil_img.mode != 'RGB':
        pil_img_rgb = pil_img.convert('RGB')
    else:
        pil_img_rgb = pil_img
    color_std = np.mean([np.std(np.array(pil_img_rgb)[:,:,c]) for c in range(3)])
    
    visual_notes = []
    if edge_density > 0.3:
        visual_notes.append('边缘丰富，结构信息密集')
    elif edge_density > 0.15:
        visual_notes.append('中等边缘密度')
    else:
        visual_notes.append('边缘稀疏，以大面积色块为主')
    if color_std > 60:
        visual_notes.append('色彩丰富')
    elif color_std > 30:
        visual_notes.append('色彩适中')
    else:
        visual_notes.append('色彩单一')
    
    if img_type == 'chart':
        horz = np.mean(np.abs(sx) > np.percentile(np.abs(sx), 90), axis=1)
        vert = np.mean(np.abs(sy) > np.percentile(np.abs(sy), 90), axis=0)
        if np.mean(horz > 0.3) > np.mean(vert > 0.3):
            visual_notes.append('水平线条多于垂直线条，可能为折线图或柱状图')
        else:
            visual_notes.append('垂直线条多于水平线条，可能为柱状图')
        numbers = re.findall(r'\d+[\.\,]\d+%?|\d+[%万股亿元]', ocr_text)
        if numbers:
            visual_notes.append(f'包含数据: {", ".join(numbers[:10])}')
    elif img_type == 'table':
        visual_notes.append('表格布局，包含行列网格结构')
        numbers = re.findall(r'\d+[\.\,]\d+%?|\d+[%万股亿元]', ocr_text)
        if numbers:
            visual_notes.append(f'含数值数据: {", ".join(numbers[:10])}')
    elif img_type == 'org_chart':
        visual_notes.append('层级组织结构图')
        names = re.findall(r'[\u4e00-\u9fff]{2,}(?:部长|总监|经理|主任|总裁|董事长|主席|长)', ocr_text)
        if names:
            visual_notes.append(f'涉及职位: {", ".join(names[:5])}')
    
    parts.append(f'[视觉特征] {"；".join(visual_notes)}')
    
    if page_context:
        context_lines = [l.strip() for l in page_context.split('\n') if l.strip() and len(l.strip()) > 5]
        important_lines = [l for l in context_lines[:10] if len(l) < 150]
        if important_lines:
            parts.append(f'[页面上下文]\n{" | ".join(important_lines[:6])}')
    
    feats_b64 = base64_encode_feats(visual_feats)
    parts.append(f'[特征向量] {feats_b64}')
    
    return '\n'.join(parts)

def base64_encode_feats(feats):
    import base64
    quantized = np.clip(feats * 32767, -32768, 32767).astype(np.int16)
    return base64.b64encode(quantized.tobytes()).decode('ascii')

def base64_decode_feats(b64_str):
    import base64
    raw = base64.b64decode(b64_str)
    quantized = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    return quantized / 32767.0

def process_all_images_multi_modal():
    """处理所有PDF图像，生成多模态特征"""
    import pytesseract
    
    if os.path.exists(VISUAL_INDEX_PATH):
        with open(VISUAL_INDEX_PATH, 'r', encoding='utf-8') as f:
            cached = json.load(f)
        print(f'[多模态索引缓存已加载] {len(cached)} 条')
        return cached
    
    print('=' * 60)
    print('[开始多模态图像语义解析]')
    print('方法: 视觉特征(512维) + OCR文本 + 页面上下文')
    print('=' * 60)
    
    all_images = []
    for pdf_path in [
        os.path.join(BASE_DIR, '招股说明书1-无水印.pdf'),
        os.path.join(BASE_DIR, '招股说明书2-无水印.pdf'),
    ]:
        if os.path.exists(pdf_path):
            doc = fitz.open(pdf_path)
            pdf_name = os.path.basename(pdf_path)
            for page_num, page in enumerate(doc):
                try:
                    image_list = page.get_images(full=True)
                    for img_idx, img_info in enumerate(image_list):
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        img_bytes = base_image["image"]
                        img_ext = base_image["ext"]
                        pil_img = Image.open(io.BytesIO(img_bytes))
                        w, h = pil_img.size
                        if w < 30 or h < 30:
                            continue
                        if w * h > 5000000:
                            continue
                        cache_key = f"{pdf_name}_p{page_num+1}_i{img_idx}.{img_ext}"
                        cache_path = os.path.join(CACHE_DIR, cache_key)
                        with open(cache_path, 'wb') as f:
                            f.write(img_bytes)
                        page_text = get_page_text(pdf_path, page_num)
                        all_images.append({
                            'page': page_num + 1,
                            'img_index': img_idx,
                            'path': cache_path,
                            'width': w, 'height': h,
                            'source': pdf_name,
                            'page_text_context': page_text[:2000] if page_text else '',
                            'pil_img': pil_img,
                        })
                except:
                    pass
            doc.close()
            count = len([x for x in all_images if x['source'] == pdf_name])
            print(f'  {pdf_name}: {count} 张图像')
    
    print(f'\n共 {len(all_images)} 张图像，开始多模态特征提取...')
    results = []
    t0 = time.time()
    
    for i, img in enumerate(all_images):
        pil_img = img['pil_img']
        page_text = img.get('page_text_context', '')
        ocr_text = pytesseract.image_to_string(pil_img, lang='chi_sim+eng').strip()
        visual_feats = extract_visual_features(pil_img)
        img_type, img_score, all_scores, eng_type = classify_image_type(pil_img, ocr_text, page_text)
        description = generate_rich_description(pil_img, ocr_text, page_text, img_type, img_score, visual_feats)
        desc_lines = description.split('\n')
        clean_desc = '\n'.join(l for l in desc_lines if not l.startswith('[特征向量]'))
        
        chunk = {
            'page': img['page'],
            'source': img['source'],
            'img_index': img['img_index'],
            'path': img['path'],
            'width': img['width'], 'height': img['height'],
            'type': img_type,
            'type_score': round(img_score, 2),
            'type_scores': {k: round(v, 2) for k, v in all_scores.items()},
            'description': clean_desc,
            'ocr_text': ocr_text[:500],
            'feature_vector': base64_encode_feats(visual_feats),
        }
        results.append(chunk)
        
        if (i + 1) % 10 == 0 or i + 1 == len(all_images):
            elapsed = time.time() - t0
            print(f'  [{i+1}/{len(all_images)}] {elapsed:.1f}s ({elapsed/(i+1):.2f}s/张)', flush=True)
    
    with open(VISUAL_INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 同时更新旧的image_descriptions.json保持兼容
    old_descriptions = [{
        'page': r['page'], 'source': r['source'],
        'img_index': r['img_index'], 'path': r['path'],
        'width': r['width'], 'height': r['height'],
        'description': r['description'],
    } for r in results]
    with open(IMAGE_INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(old_descriptions, f, ensure_ascii=False, indent=2)
    
    elapsed = time.time() - t0
    print(f'\n[完成] {len(results)} 张图像多模态解析完毕，耗时{elapsed:.1f}s')
    print(f'特征维度: 512维（颜色60+纹理60+统计24+形状9+空间32+填充327）')
    type_counts = {}
    for r in results:
        t = r['type']
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f'  {t}: {c} 张')
    return results

if __name__ == '__main__':
    process_all_images_multi_modal()
