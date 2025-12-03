"""
一个使用大语言模型（LLM）进行文物信息抽取的模块。
支持多种LLM服务提供商：Gemini、Anthropic Claude等。
"""

import json
import os
import requests
from typing import List, Dict, Any, Optional


def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_prompt_template():
    """加载提示词模板"""
    prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'extract_artifacts_prompt.txt')
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()


def call_gemini_api(prompt: str, config: dict) -> str:
    """
    调用Google Gemini API获取响应
    
    Args:
        prompt: 发送给LLM的提示词
        config: 包含API配置的字典
        
    Returns:
        str: LLM返回的文本响应
    """
    api_url = config['llm']['api_url']
    api_key = config['llm']['api_key']
    model = config['llm']['model']
    temperature = config['llm'].get('temperature', 0.7)
    max_output_tokens = config['llm'].get('max_tokens', 4096)
    
    # 构建完整的API端点URL
    endpoint = f"{api_url}/models/{model}:generateContent"
    
    # 构建请求头
    headers = {
        'Content-Type': 'application/json',
        'x-goog-api-key': api_key
    }
    
    # 构建请求体（Gemini API格式）
    payload = {
        'contents': [
            {
                'parts': [
                    {
                        'text': prompt
                    }
                ]
            }
        ],
        'generationConfig': {
            'temperature': temperature,
            'maxOutputTokens': max_output_tokens
        }
    }
    
    try:
        # 增加超时时间到300秒（5分钟）
        response = requests.post(endpoint, json=payload, headers=headers, timeout=300)
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        
        # 处理Gemini API响应格式
        if 'candidates' in result and len(result['candidates']) > 0:
            candidate = result['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                parts = candidate['content']['parts']
                if len(parts) > 0 and 'text' in parts[0]:
                    return parts[0]['text']
        
        # 如果格式不匹配，尝试其他可能的格式
        if 'text' in result:
            return result['text']
        
        raise ValueError(f"无法解析Gemini API响应: {result}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Gemini API调用失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"响应状态码: {e.response.status_code}")
            try:
                error_detail = e.response.json()
                print(f"错误详情: {json.dumps(error_detail, ensure_ascii=False, indent=2)}")
            except:
                print(f"响应内容: {e.response.text}")
        raise


def call_anthropic_api(prompt: str, config: dict) -> str:
    """
    调用Anthropic Claude API获取响应
    
    Args:
        prompt: 发送给LLM的提示词
        config: 包含API配置的字典
        
    Returns:
        str: LLM返回的文本响应
    """
    api_url = config['llm']['api_url']
    api_key = config['llm']['api_key']
    model = config['llm']['model']
    temperature = config['llm'].get('temperature', 0.7)
    max_tokens = config['llm'].get('max_tokens', 1024)
    
    # 构建请求头
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01'
    }
    
    # 构建请求体（Anthropic API格式）
    payload = {
        'model': model,
        'messages': [
            {
                'role': 'user',
                'content': prompt
            }
        ],
        'temperature': temperature,
        'max_tokens': max_tokens
    }
    
    try:
        # 增加超时时间到300秒（5分钟）
        response = requests.post(api_url, json=payload, headers=headers, timeout=300)
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        
        # 处理Anthropic API响应格式
        if 'content' in result:
            if isinstance(result['content'], list):
                return result['content'][0]['text']
            else:
                return result['content']
        elif 'text' in result:
            return result['text']
        elif 'message' in result and 'content' in result['message']:
            content = result['message']['content']
            if isinstance(content, list):
                return content[0]['text']
            return content
        
        raise ValueError(f"无法解析Anthropic API响应: {result}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Anthropic API调用失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"响应状态码: {e.response.status_code}")
            print(f"响应内容: {e.response.text}")
        raise


def call_coze_api(prompt: str, config: dict) -> str:
    """
    调用Coze.cn API获取响应（使用v3 API）
    
    Args:
        prompt: 发送给LLM的提示词
        config: 包含API配置的字典
        
    Returns:
        str: LLM返回的文本响应
    """
    api_url = config['llm']['api_url']
    api_key = config['llm']['api_key']
    bot_id = config['llm']['bot_id']
    
    # 构建请求头
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    # 使用正确的Coze API格式
    # 参考: https://www.coze.cn/open/docs/developer_guides/coze_api_overview
    chat_url = f"{api_url}/open_api/v2/chat"
    
    # 正确的请求格式: bot_id, user, query, stream
    chat_payload = {
        'bot_id': str(bot_id),
        'user': 'user_001',  # 用户标识符
        'query': prompt,
        'stream': True  # 改为流式响应以避免超时
    }
    
    try:
        # 开启流式接收，timeout仅作为连接超时
        chat_response = requests.post(chat_url, json=chat_payload, headers=headers, timeout=60, stream=True)
        chat_response.raise_for_status()
        
        reply = ""
        print("⏳ 正在接收Coze流式响应...", end="", flush=True)
        
        # 用于跟踪当前的SSE事件类型
        current_event = None
        
        for line in chat_response.iter_lines():
            if not line:
                continue
                
            decoded_line = line.decode('utf-8').strip()
            
            # 强力调试：打印所有接收到的行
            print(f"RAW: {decoded_line}")
            
            # 处理SSE事件类型行
            if decoded_line.startswith('event:'):
                current_event = decoded_line[6:].strip()
                continue
            
            if decoded_line.startswith('data:'):
                data_str = decoded_line[5:].strip()
                try:
                    data = json.loads(data_str)
                    
                    # 优先使用SSE header中的event，如果没有则尝试从JSON中获取
                    event = current_event or data.get('event')
                    
                    # --- 策略1: V2/V3 message事件 ---
                    if event == 'message':
                        message = data.get('message', {})
                        if message.get('role') == 'assistant' and message.get('type') == 'answer':
                            content = message.get('content', '')
                            reply += content
                            
                    # --- 策略2: V3 conversation.message.delta ---
                    elif event == 'conversation.message.delta':
                        # V3 delta通常直接在顶层有content
                        if 'content' in data:
                            reply += data['content']
                        # 或者在delta字段里
                        elif 'delta' in data and 'content' in data['delta']:
                            reply += data['delta']['content']
                            
                    # --- 策略3: V3 conversation.message.completed ---
                    # 有时候delta没收到，completed里会有完整内容
                    elif event == 'conversation.message.completed':
                        if 'content' in data and not reply: # 只有当reply为空时才使用completed的内容，避免重复
                             reply += data['content']

                    # --- 策略4: 盲猜模式 (只要是assistant的answer就收) ---
                    elif data.get('role') == 'assistant' and data.get('type') == 'answer':
                        content = data.get('content', '')
                        reply += content
                        
                    # --- 策略5: 最后的万能匹配 ---
                    elif 'content' in data and data.get('role') == 'assistant':
                         # 排除空内容
                         if data['content']:
                             reply += data['content']

                    # 结束事件
                    elif event == 'done':
                        break
                        
                except json.JSONDecodeError:
                    continue
        
        print(" 完成")
        
        if not reply:
            # 如果流式失败，记录详细的响应头以便调试
            print(f"\n❌ Coze流式响应为空。Headers: {chat_response.headers}")
            raise ValueError(f"Coze流式响应未返回有效内容")
        
        return reply
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Coze API调用失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"响应状态码: {e.response.status_code}")
            try:
                error_detail = e.response.json()
                print(f"错误详情: {json.dumps(error_detail, ensure_ascii=False, indent=2)}")
            except:
                print(f"响应内容: {e.response.text}")
        raise


def call_llm_api(prompt: str, config: dict) -> str:
    """
    通用的LLM API调用函数，根据配置的provider自动选择对应的API调用方法
    
    Args:
        prompt: 发送给LLM的提示词
        config: 包含API配置的字典
        
    Returns:
        str: LLM返回的文本响应
    """
    provider = config['llm'].get('provider', 'coze').lower()
    
    if provider == 'coze':
        return call_coze_api(prompt, config)
    elif provider == 'gemini':
        return call_gemini_api(prompt, config)
    elif provider == 'anthropic' or provider == 'claude':
        return call_anthropic_api(prompt, config)
    else:
        raise ValueError(f"不支持的LLM提供商: {provider}。支持的提供商: coze, gemini, anthropic")


def repair_truncated_json(json_str: str) -> str:
    """
    尝试修复截断的JSON字符串（针对列表格式）
    """
    json_str = json_str.strip()
    
    # 1. 尝试闭合未闭合的字符串
    if json_str.count('"') % 2 != 0:
        # 找到最后一个 " 的位置
        last_quote = json_str.rfind('"')
        if last_quote != -1:
            # 如果最后一个引号前面是转义符，说明它不是结束引号，那我们可能需要补一个
            # 但这里简化处理，直接补一个 "
            json_str += '"'
            
    # 2. 尝试闭合括号
    stack = []
    for char in json_str:
        if char == '{':
            stack.append('}')
        elif char == '[':
            stack.append(']')
        elif char == '}' or char == ']':
            if stack and stack[-1] == char:
                stack.pop()
    
    # 补全剩余的闭合括号
    while stack:
        closer = stack.pop()
        json_str += closer
        
    return json_str


def extract_json_from_response(response_text: str) -> Any:
    """
    从LLM响应中提取JSON内容（支持对象或数组）
    
    Args:
        response_text: LLM返回的文本
        
    Returns:
        dict or list: 解析后的JSON对象或列表
    """
    text = response_text.strip()
    
    # 1. 优先尝试从 Markdown 代码块中提取
    # 使用 split 而不是正则，避免正则匹配内部字符的问题
    if '```' in text:
        blocks = text.split('```')
        # 代码块通常在奇数索引位置 (text -> ```code``` -> text)
        for i in range(1, len(blocks), 2):
            block = blocks[i].strip()
            # 去掉可能的语言标识
            if block.startswith('json'):
                block = block[4:].strip()
            
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                # 尝试修复代码块内的截断
                try:
                    repaired = repair_truncated_json(block)
                    return json.loads(repaired)
                except:
                    continue
    
    # 2. 尝试直接解析整个文本
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试修复整个文本
        try:
            repaired = repair_truncated_json(text)
            if repaired != text:
                return json.loads(repaired)
        except:
            pass
    
    # 3. 智能提取：寻找最外层的 [ ... ] 或 { ... }
    # 使用栈逻辑来匹配，比正则更可靠
    
    # 确定搜索的起始符号
    start_markers = ['[', '{']
    # 优先搜索靠前的
    first_bracket = text.find('[')
    first_brace = text.find('{')
    
    if first_bracket == -1 and first_brace == -1:
         raise ValueError(f"无法从响应中提取有效的JSON。未找到 [ 或 {{。")
    
    # 决定优先尝试哪种结构
    if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        markers = ['[', '{']
    else:
        markers = ['{', '[']
        
    for start_char in markers:
        end_char = ']' if start_char == '[' else '}'
        start_idx = text.find(start_char)
        
        if start_idx != -1:
            # 尝试找到匹配的结束括号
            balance = 0
            in_string = False
            escape = False
            
            for i in range(start_idx, len(text)):
                char = text[i]
                
                if escape:
                    escape = False
                    continue
                    
                if char == '\\':
                    escape = True
                    continue
                    
                if char == '"':
                    in_string = not in_string
                    continue
                    
                if not in_string:
                    if char == start_char:
                        balance += 1
                    elif char == end_char:
                        balance -= 1
                        if balance == 0:
                            # 找到完整闭合
                            candidate = text[start_idx:i+1]
                            try:
                                return json.loads(candidate)
                            except:
                                pass
                                
            # 如果循环结束还没闭合，说明截断了
            if balance > 0:
                try:
                    candidate = text[start_idx:]
                    repaired = repair_truncated_json(candidate)
                    return json.loads(repaired)
                except:
                    pass

    raise ValueError(f"无法从响应中提取有效的JSON。")


def extract_from_text_with_llm(tomb_text: str, template_keywords: List[str] = None) -> List[Dict[str, Any]]:
    """
    使用LLM从指定墓葬的文本中提取文物信息。

    这是正则表达式抽取器的进化版，能更好地处理不一致的行文。

    Args:
        tomb_text (str): 墓葬的文本内容。
        template_keywords (List[str]): 模板中定义的文化特征单元关键词列表（可选）。

    Returns:
        list: 一个字典列表，每个字典代表一个文物实例。
    """
    try:
        # 加载配置和提示词模板
        config = load_config()
        prompt_template = load_prompt_template()
        
        # 构建完整的提示词
        prompt = prompt_template.replace('{tomb_text}', tomb_text)
        
        # 如果有模板关键词，可以添加到提示词中（可选）
        if template_keywords:
            keywords_str = '、'.join([kw for kw in template_keywords if kw])
            if keywords_str:
                prompt += f"\n\n注意：请特别关注以下文化特征单元：{keywords_str}"
        
        provider = config['llm'].get('provider', 'coze')
        if provider == 'coze':
            bot_id = config['llm'].get('bot_id', 'N/A')
            print(f"📤 正在调用LLM API (提供商: {provider}, Bot ID: {bot_id})...")
        else:
            model = config['llm'].get('model', 'N/A')
            print(f"📤 正在调用LLM API (提供商: {provider}, 模型: {model})...")
        
        # 调用LLM API（自动选择对应的提供商）
        response_text = call_llm_api(prompt, config)
        
        # 从响应中提取JSON
        result = extract_json_from_response(response_text)
        
        # 验证结果格式
        if 'artifacts' not in result:
            print("⚠️ 警告: LLM响应中未找到'artifacts'字段")
            print(f"响应内容: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")
            return []
        
        artifacts = result['artifacts']
        
        # 为每个文物添加LLM无法直接获取的常量字段（如果需要）
        for artifact in artifacts:
            # 确保所有必需字段存在
            if '核心实体类型' not in artifact:
                artifact['核心实体类型'] = 'E22'
            if '关系' not in artifact:
                artifact['关系'] = 'P45 consists of'
            if '中间类' not in artifact:
                artifact['中间类'] = 'E57 Material (材料)'
        
        print(f"✅ 成功提取 {len(artifacts)} 个文物信息")
        return artifacts
        
    except Exception as e:
        print(f"❌ 提取过程中发生错误: {e}")
        
        # 补救机制：保存失败的原始响应，防止数据丢失
        if 'response_text' in locals():
            try:
                from datetime import datetime
                # 确保 logs 目录存在
                log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs', 'failed_responses')
                os.makedirs(log_dir, exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = os.path.join(log_dir, f"failed_response_{timestamp}.txt")
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"Error: {str(e)}\n")
                    f.write(f"Prompt Snippet: {prompt[:500]}...\n")
                    f.write("-" * 50 + "\n")
                    f.write(response_text)
                print(f"💾 已将失败的原始响应保存至: {filename}")
            except Exception as save_err:
                print(f"⚠️ 保存失败响应时发生错误: {save_err}")

        import traceback
        traceback.print_exc()
        return []
