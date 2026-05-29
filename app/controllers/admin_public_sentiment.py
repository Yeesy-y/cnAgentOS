# 智能舆情分析控制器
import tornado.web
import json
import urllib.request
import urllib.error
import os
from app.controllers.admin_base import AdminBaseHandler
from app.models.db import get_connection


class PublicSentimentIndexHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render('admin_public_sentiment.html', 
                    title='智能舆情分析 - AI 智能瞭望系统',
                    username=self.current_user if isinstance(self.current_user, str) else self.current_user.get('username', 'Admin'),
                    active_menu='public_sentiment')


class SentimentAnalysisHandler(AdminBaseHandler):
    """舆情分析 API 处理类"""
    
    # 高风险敏感词分类（用于初步筛选）
    SENSITIVE_KEYWORDS = {
        'national_security': ['国家安全', '颠覆政权', '分裂国家', '恐怖主义'],
        'political_sensitivity': ['政治敏感', '领导人', '政府政策', '党史'],
        'social_instability': ['抗议', '示威', '暴动', '群体性事件'],
        'illegal_content': ['色情', '赌博', '毒品', '违法']
    }
    
    def post(self):
        try:
            content_type = self.get_argument('type', 'text')
            text_content = self.get_argument('content', '')
            
            if not text_content.strip():
                self.write(json.dumps({
                    'success': False,
                    'message': '请输入待分析的文本内容'
                }, ensure_ascii=False))
                return
            
            # 调用 DeepSeek API 进行风险分析
            risk_result = self.analyze_with_deepseek(text_content)
            
            # 同时进行关键词初步检测
            keyword_warnings = self.detect_sensitive_keywords(text_content)
            
            result = {
                'success': True,
                'data': {
                    'original_text': text_content,
                    'risk_level': risk_result.get('risk_level', 'low'),
                    'risk_score': risk_result.get('risk_score', 0),
                    'analysis': risk_result.get('analysis', ''),
                    'recommendations': risk_result.get('recommendations', []),
                    'keyword_warnings': keyword_warnings,
                    'warning_count': len(keyword_warnings)
                }
            }
            
            self.write(json.dumps(result, ensure_ascii=False))
            
        except Exception as e:
            self.write(json.dumps({
                'success': False,
                'message': f'分析失败：{str(e)}'
            }, ensure_ascii=False))
    
    def analyze_with_deepseek(self, text_content):
        """使用 DeepSeek API 分析文本风险等级"""
        
        # 从环境变量或配置中获取 API Key
        api_key = os.environ.get('DEEPSEEK_API_KEY', '57d5122baa594a378e450640b2b75f07.6NDocdi5MfECjcLr')
        
        # 构建系统提示词
        system_prompt = """你是一个专业的舆情风险评估专家。你的任务是分析给定的中文文本，评估其可能的风险等级，并提供详细的分析报告。

请按照以下标准进行评估：

1. **风险等级定义**：
   - 🔴 高危 (Risk Score: 8-10)：涉及国家安全、政治敏感、严重违法等内容，必须立即预警
   - 🟡 中危 (Risk Score: 5-7)：可能存在一定风险，需要重点关注和引导
   - 🟢 低危 (Risk Score: 1-4)：基本安全，风险较低

2. **分析维度**：
   - 政治敏感性
   - 国家安全相关
   - 社会稳定影响
   - 法律法规合规性
   - 社会道德伦理

3. **输出要求**：
   - 给出明确的风险等级和分数（0-10）
   - 详细解释为什么判断为该风险等级
   - 提供具体的改进建议或注意事项
   - 如果检测到敏感内容，明确列出并说明原因

请用简洁、专业的中文进行分析，确保报告实用且易于理解。"""

        # 构建用户消息
        user_message = f"""请对以下文本进行舆情风险评估：

{text_content}

请严格按照上述标准进行分析，并给出风险评估结果。"""

        # 构建 API 请求
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        data = {
            "model": "deepseek-v4-pro",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
            "stream": False
        }
        
        try:
            request = urllib.request.Request(url, 
                                             data=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                                             headers=headers,
                                             method='POST')
            
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                analysis_text = ''
                risk_level = 'low'
                risk_score = 0
                
                if result.get('choices'):
                    analysis_text = result['choices'][0]['message']['content']
                    
                    # 尝试从回复中提取风险等级和分数
                    if '高危' in analysis_text or '8' in analysis_text[-10:] or '9' in analysis_text[-10:] or '10' in analysis_text[-10:]:
                        risk_level = 'high'
                        risk_score = max(8, min(int(analysis_text[-2]), 10))
                    elif '中危' in analysis_text or '5' in analysis_text[-10:] or '6' in analysis_text[-10:] or '7' in analysis_text[-10:]:
                        risk_level = 'medium'
                        risk_score = max(5, min(int(analysis_text[-2]), 7))
                    else:
                        risk_level = 'low'
                        risk_score = min(4, max(1, int(analysis_text[-2]) if analysis_text[-2].isdigit() else 2))
                
                return {
                    'analysis': analysis_text,
                    'risk_level': risk_level,
                    'risk_score': risk_score
                }
                
        except urllib.error.URLError as e:
            return {
                'analysis': f'API 调用失败：{str(e)}',
                'risk_level': 'unknown',
                'risk_score': 0
            }
        except Exception as e:
            return {
                'analysis': f'分析过程出错：{str(e)}',
                'risk_level': 'unknown',
                'risk_score': 0
            }
    
    def detect_sensitive_keywords(self, text_content):
        """基于关键词的检测"""
        warnings = []
        
        for category, keywords in self.SENSITIVE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_content:
                    warnings.append({
                        'category': category,
                        'keyword': keyword,
                        'severity': 'high' if category in ['national_security', 'political_sensitivity'] else 'medium'
                    })
        
        return warnings


class WatchDataSentimentHandler(AdminBaseHandler):
    """监控数据舆情分析"""
    
    def post(self):
        try:
            conn = get_connection()
            cursor = conn.execute("""
                SELECT id, keyword, title, content, create_at
                FROM watch_data
                ORDER BY create_at DESC
                LIMIT 10
            """)
            
            recent_data = [dict(row) for row in cursor.fetchall()]
            
            results = []
            for item in recent_data:
                combined_text = f"{item.get('keyword', '')} {item.get('title', '')} {item.get('content', '')}"
                
                if combined_text.strip():
                    risk_result = self.analyze_risk(combined_text)
                    results.append({
                        'id': item['id'],
                        'keyword': item.get('keyword', ''),
                        'title': item.get('title', ''),
                        'risk_level': risk_result.get('risk_level', 'low'),
                        'risk_score': risk_result.get('risk_score', 0)
                    })
            
            self.write(json.dumps({
                'success': True,
                'data': results
            }, ensure_ascii=False))
            
        except Exception as e:
            self.write(json.dumps({
                'success': False,
                'message': str(e)
            }, ensure_ascii=False))
    
    def analyze_risk(self, text):
        """简化的风险检测"""
        # 这里可以集成 DeepSeek API 或本地规则
        sensitive_words = ['敏感', '危险', '违法', '违规', '危害']
        score = sum(1 for word in sensitive_words if word in text)
        
        if score >= 3:
            return {'risk_level': 'high', 'risk_score': 8}
        elif score >= 1:
            return {'risk_level': 'medium', 'risk_score': 5}
        else:
            return {'risk_level': 'low', 'risk_score': 2}


class ChatDataSentimentHandler(AdminBaseHandler):
    """聊天数据舆情分析"""
    
    def post(self):
        try:
            conn = get_connection()
            cursor = conn.execute("""
                SELECT cm.id, cm.content, cm.create_at, cc.title as conversation_title
                FROM chat_messages cm
                LEFT JOIN chat_conversations cc ON cm.conversation_id = cc.id
                WHERE cm.role = 'user'
                ORDER BY cm.create_at DESC
                LIMIT 10
            """)
            
            recent_chats = [dict(row) for row in cursor.fetchall()]
            
            results = []
            for chat in recent_chats:
                text = chat.get('content', '')
                if text.strip():
                    risk_result = self.analyze_risk(text)
                    results.append({
                        'id': chat['id'],
                        'content_preview': text[:100] + '...' if len(text) > 100 else text,
                        'conversation_title': chat.get('conversation_title', ''),
                        'risk_level': risk_result.get('risk_level', 'low'),
                        'risk_score': risk_result.get('risk_score', 0),
                        'create_at': chat.get('create_at', '')
                    })
            
            self.write(json.dumps({
                'success': True,
                'data': results
            }, ensure_ascii=False))
            
        except Exception as e:
            self.write(json.dumps({
                'success': False,
                'message': str(e)
            }, ensure_ascii=False))
    
    def analyze_risk(self, text):
        """简化的风险检测"""
        sensitive_words = ['敏感', '危险', '违法', '违规', '危害']
        score = sum(1 for word in sensitive_words if word in text)
        
        if score >= 3:
            return {'risk_level': 'high', 'risk_score': 8}
        elif score >= 1:
            return {'risk_level': 'medium', 'risk_score': 5}
        else:
            return {'risk_level': 'low', 'risk_score': 2}
