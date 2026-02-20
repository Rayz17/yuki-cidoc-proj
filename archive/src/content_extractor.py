"""
一个用于从考古报告中提取和分割文本内容的工具。
"""

import re

def split_by_tomb(full_text: str) -> dict:
    """
    将完整的考古报告文本按『墓葬』进行分割。

    Args:
        full_text (str): 报告的完整文本内容。

    Returns:
        dict: 一个字典，key为墓葬编号 (如 '一号墓' 或 'M1'), value为对应的文本内容。
    """
    # 支持多种墓葬标题格式：
    # 格式1: "# 第一节 一号墓" 或 "# 第三节 三号墓"
    # 格式2: "## M1 墓葬" 或 "## M1"
    # 格式3: "## 一号墓" 或 "# 一号墓"
    patterns = [
        r'^#{1,3} (?:第[一二三四五六七八九十]+节\s+)?(一|二|三|四|五|六|七|八|九|十|十一|十二)号墓',
        r'^#{1,3}\s*M(\d+)(?:\s*墓葬)?',
        r'^#{1,3}\s*(一|二|三|四|五|六|七|八|九|十|十一|十二)号墓'
    ]

    # 初始化结果字典和临时变量
    result = {}
    current_tomb = None
    current_content = []

    for line in full_text.split('\n'):
        # 检查该行是否是墓葬标题
        matched = False
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                # 如果已经有当前墓葬，先保存
                if current_tomb:
                    result[current_tomb] = '\n'.join(current_content).strip()
                    current_content = []
                # 开始新的墓葬
                if 'M' in pattern:
                    current_tomb = f"M{match.group(1)}"
                else:
                    current_tomb = f"{match.group(1)}号墓"
                matched = True
                break
        
        if not matched and current_tomb:
            # 如果当前在某个墓葬的文本中，就添加该行
            current_content.append(line)

    # 不要忘记保存最后一个墓葬
    if current_tomb and current_content:
        result[current_tomb] = '\n'.join(current_content).strip()

    return result

# 示例用法，您可以在主脚本中这样调用：
# with open('/path/to/full.md', 'r', encoding='utf-8') as f:
#     full_text = f.read()
#
# tomb_contents = split_by_tomb(full_text)
# print(tomb_contents['一号墓']) # 打印一号墓的全部文本
