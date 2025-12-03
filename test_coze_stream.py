import requests
import json
import os
import sys

def test_coze_stream():
    # 加载配置
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"无法加载配置文件: {e}")
        return

    api_url = config['llm'].get('api_url', 'https://api.coze.cn')
    api_key = config['llm'].get('api_key')
    bot_id = config['llm'].get('bot_id')

    if not api_key or not bot_id:
        print("配置中缺少 api_key 或 bot_id")
        return

    print(f"正在测试 Coze 流式 API...")
    print(f"URL: {api_url}/open_api/v2/chat")
    print(f"Bot ID: {bot_id}")

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    chat_payload = {
        'bot_id': str(bot_id),
        'user': 'test_user_001',
        'query': '你好，请用JSON格式输出一个简单的陶器描述，包含名称和尺寸。',
        'stream': True
    }

    try:
        response = requests.post(
            f"{api_url}/open_api/v2/chat", 
            json=chat_payload, 
            headers=headers, 
            timeout=60,
            stream=True
        )
        response.raise_for_status()

        print("连接建立成功，开始接收流式数据:")
        print("-" * 50)

        full_content = ""
        
        for line in response.iter_lines():
            if not line:
                continue
            
            decoded_line = line.decode('utf-8')
            print(f"收到数据行: {decoded_line[:100]}..." if len(decoded_line) > 100 else f"收到数据行: {decoded_line}")
            
            if decoded_line.startswith('data:'):
                data_str = decoded_line[5:].strip()
                try:
                    data = json.loads(data_str)
                    event = data.get('event')
                    
                    if event == 'message':
                        message = data.get('message', {})
                        if message.get('role') == 'assistant' and message.get('type') == 'answer':
                            content = message.get('content', '')
                            print(f"  -> 提取内容: {content}")
                            full_content += content
                    elif event == 'done':
                        print("  -> 收到结束信号")
                        
                except json.JSONDecodeError:
                    print("  -> JSON解析失败")

        print("-" * 50)
        print(f"最终完整内容: {full_content}")
        
        if full_content:
            print("✅ 测试成功！")
        else:
            print("❌ 测试失败：未收到内容")

    except Exception as e:
        print(f"❌ 请求失败: {e}")

if __name__ == "__main__":
    test_coze_stream()

