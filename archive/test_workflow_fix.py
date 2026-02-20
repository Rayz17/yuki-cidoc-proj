"""
测试workflow修复
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.content_extractor import split_by_tomb

# 测试split_by_tomb函数
test_text = """
# 第一节 一号墓

这是一号墓的内容。
出土陶器3件。

## M2 墓葬

这是M2的内容。
出土玉器5件。

## 三号墓

这是三号墓的内容。
"""

print("测试 split_by_tomb 函数:")
print("=" * 60)

tomb_dict = split_by_tomb(test_text)
print(f"返回类型: {type(tomb_dict)}")
print(f"墓葬数量: {len(tomb_dict)}")
print(f"墓葬列表: {list(tomb_dict.keys())}")

# 转换为列表格式
tomb_blocks = list(tomb_dict.items())
print(f"\n转换后类型: {type(tomb_blocks)}")
print(f"第一个元素: {tomb_blocks[0] if tomb_blocks else 'None'}")

# 测试enumerate
print("\n测试 enumerate:")
for i, tomb_block in enumerate(tomb_blocks):
    tomb_name, tomb_text = tomb_block
    print(f"  {i+1}. {tomb_name}: {len(tomb_text)} 字符")

print("\n✅ 测试通过！")

