"""
法律知识检索增强生成模块 (Legal RAG)
基于 TF-IDF + jieba 分词 + 本地法律知识库
兼容原 LLM 接口，可无缝替换
"""
import os
import json
import jieba
import re
import sys
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# 知识库路径
KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "legal_kb")


class LegalRetriever:
    """法律条文检索器 - TF-IDF + jieba 分词"""
    
    def __init__(self, kb_dir=KB_DIR):
        self.kb_dir = kb_dir
        self.documents = []       # 原始文档列表
        self.metadata = []        # 元数据 (法律名称, 章节, 条款号)
        self.vectorizer = None
        self.tfidf_matrix = None
        self.load_knowledge_base()
    
    def load_knowledge_base(self):
        """加载法律知识库"""
        if not os.path.exists(self.kb_dir):
            os.makedirs(self.kb_dir, exist_ok=True)
            print(f"[LegalRAG] 知识库目录 {self.kb_dir} 已创建，请放入法律文本文件")
            return
        
        files = [f for f in os.listdir(self.kb_dir) if f.endswith(('.txt', '.json', '.md'))]
        if not files:
            print("[LegalRAG] 知识库目录为空，请先导入法律条文")
            return
        
        print(f"[LegalRAG] 正在加载 {len(files)} 个法律文件...")
        for fname in files:
            fpath = os.path.join(self.kb_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(fpath, 'r', encoding='gbk') as f:
                    content = f.read()
            
            # 按条款分割（支持 "第X条" 格式）
            articles = self._split_articles(content, fname)
            self.documents.extend(articles['texts'])
            self.metadata.extend(articles['metadatas'])
        
        print(f"[LegalRAG] 共加载 {len(self.documents)} 条法律条款")
        self._build_index()
    
    def _split_articles(self, content, filename):
        """将法律文本按条款分割"""
        texts = []
        metadatas = []
        
        # 提取法律名称（文件名去掉扩展名）
        law_name = os.path.splitext(filename)[0]
        
        # 匹配 "第X条" 模式
        pattern = r'(第[一二三四五六七八九十百零\d]+条[　 ]*.*?)(?=第[一二三四五六七八九十百零\d]+条|\Z)'
        matches = re.findall(pattern, content, re.DOTALL)
        
        if matches:
            for i, article in enumerate(matches):
                article = article.strip()
                if len(article) < 10:  # 过短的条款跳过
                    continue
                # 提取条款编号
                title_match = re.match(r'(第[^条]+条)', article)
                title = title_match.group(1) if title_match else f"第{i+1}条"
                
                texts.append(article)
                metadatas.append({
                    'law': law_name,
                    'article': title,
                    'source': filename
                })
        else:
            # 如果没有 "第X条" 格式，整篇作为一个文档
            # 按段落分割
            paragraphs = [p.strip() for p in content.split('\n\n') if len(p.strip()) > 30]
            for i, para in enumerate(paragraphs):
                texts.append(para)
                metadatas.append({
                    'law': law_name,
                    'article': f'段落{i+1}',
                    'source': filename
                })
        
        return {'texts': texts, 'metadatas': metadatas}
    
    def _build_index(self):
        """构建 TF-IDF 索引"""
        if not self.documents:
            return
        
        # jieba 分词器
        def tokenizer(text):
            return [w for w in jieba.cut(text) if len(w.strip()) > 1 and not w.isspace()]
        
        self.vectorizer = TfidfVectorizer(
            tokenizer=tokenizer,
            max_features=10000,
            norm='l2'
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(self.documents)
        print(f"[LegalRAG] TF-IDF 索引构建完成，词汇量: {len(self.vectorizer.get_feature_names_out())}")
    
    def retrieve(self, query, top_k=5):
        """检索与查询最相关的法律条款"""
        if not self.documents or self.vectorizer is None:
            return []
        
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.tfidf_matrix)[0]
        
        # 获取top_k结果
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # 只返回有相关性的结果
                results.append({
                    'text': self.documents[idx],
                    'metadata': self.metadata[idx],
                    'score': float(scores[idx])
                })
        
        return results


class LegalRAG:
    """
    法律RAG - 检索增强的法律咨询模块
    完全兼容原 LLM 接口（generate 方法）
    """
    
    def __init__(self, mode='api', model_path='', api_key=None, proxy_url=None, prefix_prompt=''):
        self.mode = mode
        self.model_path = model_path or 'gpt-4o-mini'
        self.api_key = api_key
        self.proxy_url = proxy_url
        self.prefix_prompt = prefix_prompt
        
        # 初始化法律检索器
        print("[LegalRAG] 正在初始化法律知识库...")
        self.retriever = LegalRetriever()
        
        # 初始化底层 LLM（用 ChatGPT API 或本地模型）
        self._init_llm()
    
    def _init_llm(self):
        """初始化底层 LLM"""
        api_key = self.api_key or os.environ.get('OPENAI_API_KEY', '')
        if api_key:
            try:
                from .ChatGPT import ChatGPT
                self.llm = ChatGPT(
                    model_path=self.model_path or 'gpt-4o-mini',
                    api_key=api_key,
                    proxy_url=self.proxy_url
                )
                print(f"[LegalRAG] 底层 LLM 初始化完成: ChatGPT({self.model_path})")
                return
            except Exception as e:
                print(f"[LegalRAG] ChatGPT 初始化失败: {e}")
        
        print("[LegalRAG] 未配置API key，使用内置法律知识库直接回答模式")
        self.llm = None
    
    def _build_legal_prompt(self, question, retrieved_docs):
        """构建法律咨询的增强提示词"""
        
        # 系统角色设定
        system_prompt = """你是「法小助」—— 一位专业、严谨的中国法律咨询助手。
你的职责是：
1. 根据中国现行法律法规回答用户的法律问题
2. 回答必须引用具体的法律条款（法律名称、第X条）
3. 如果检索到的法条不足以回答，明确说明"根据现有信息无法完全回答"
4. 用通俗易懂的语言解释法律条文
5. 提示用户如有需要应咨询专业律师
6. 禁止提供虚假或编造的法律信息
7. 回答结构：法条引用 → 解读 → 建议

注意：你提供的只是法律信息参考，不构成正式法律意见。"""
        
        # 构建检索到的法律上下文
        legal_context = ""
        if retrieved_docs:
            legal_context = "【相关法律条文】\n"
            for i, doc in enumerate(retrieved_docs, 1):
                meta = doc['metadata']
                legal_context += f"\n{i}. 《{meta['law']}》{meta['article']}（相关度: {doc['score']:.2f}）\n"
                legal_context += f"   {doc['text'][:500]}\n"
        
        # 构建完整prompt
        full_prompt = f"{system_prompt}\n\n"
        if legal_context:
            full_prompt += f"{legal_context}\n\n"
        full_prompt += f"【用户问题】\n{question}\n\n"
        full_prompt += "【回答】\n请基于上述法律条文回答，引用具体条款。"
        
        return full_prompt
    
    def generate(self, prompt):
        """
        生成法律咨询回答
        完全兼容原 LLM.generate(question) 接口
        
        Args:
            prompt: 用户问题
            
        Returns:
            str: 法律咨询回答
        """
        # 1. 检索相关法律条款
        retrieved = self.retriever.retrieve(prompt, top_k=5)
        
        # 2. 构建增强prompt
        enhanced_prompt = self._build_legal_prompt(prompt, retrieved)
        
        # 3. 调用底层LLM
        if self.llm:
            try:
                answer = self.llm.generate(enhanced_prompt)
                return answer
            except Exception as e:
                print(f"[LegalRAG] LLM调用失败: {e}")
                return self._fallback_answer(prompt, retrieved)
        else:
            return self._fallback_answer(prompt, retrieved)
    
    def _fallback_answer(self, question, retrieved_docs):
        """LLM不可用时的兜底回答 - 结构化法律咨询"""
        if not retrieved_docs:
            return (f"抱歉，关于「{question}」这个问题，我的法律知识库中没有找到直接相关的条文。\n\n"
                    f"💡 建议：\n"
                    f"1. 换个关键词重新提问\n"
                    f"2. 拨打 12348 法律服务热线咨询\n"
                    f"3. 咨询专业律师")
        
        # 去重（同一法律的同一条款只显示一次）
        seen = set()
        unique_docs = []
        for doc in retrieved_docs:
            key = f"{doc['metadata']['law']}|{doc['metadata']['article']}"
            if key not in seen:
                seen.add(key)
                unique_docs.append(doc)
        
        answer = f"⚖️ **关于「{question}」的法律参考**\n\n"
        answer += f"根据检索到的相关法律条文，为您提供以下信息：\n\n"
        
        for i, doc in enumerate(unique_docs[:3], 1):
            meta = doc['metadata']
            text = doc['text'][:500]
            law_name = meta['law']
            article_name = meta['article']
            answer += f"**{i}. 《{law_name}》{article_name}**\n"
            answer += f"> {text}\n\n"
        
        answer += "---\n"
        answer += "⚠️ **温馨提示：** 以上信息仅供参考，不构成正式法律意见。\n"
        answer += "如涉及重大法律事务，建议咨询专业律师或拨打 **12348** 法律服务热线。"
        
        return answer


# 知识库构建工具函数
def build_kb_from_texts(law_name, texts, kb_dir=KB_DIR):
    """将法律文本列表写入知识库文件"""
    os.makedirs(kb_dir, exist_ok=True)
    fpath = os.path.join(kb_dir, f"{law_name}.txt")
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(texts))
    print(f"[LegalRAG] 知识库文件已写入: {fpath}")
    return fpath


if __name__ == '__main__':
    # 测试
    rag = LegalRAG()
    test_q = "离婚财产怎么分割？"
    print(f"\n测试问题: {test_q}")
    print(f"检索结果: {json.dumps(rag.retriever.retrieve(test_q, top_k=2), ensure_ascii=False, indent=2)}")