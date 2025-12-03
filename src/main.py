"""
主脚本：端到端执行文物信息抽取流程。
"""

import argparse
from report_processor import ReportProcessor
from content_extractor import split_by_tomb
from automated_extractor import extract_from_text_with_llm as extract_from_text
from database_manager import DatabaseManager


def main(report_path, template_path, db_path='database/artifacts.db'):
    """
    执行完整的提取流程。
    """
    print("开始执行文物信息抽取流程...")

    # 阶段1: 从模板加载数据结构
    print("[Step 1/4] 加载数据结构模板...")
    processor = ReportProcessor()
    template_data = processor.load_template(template_path)
    # 提取文化特征单元字段（用于指导LLM抽取）
    template_keywords = [item.get('文化特征单元（以陶器为例子）', '') for item in template_data if item.get('文化特征单元（以陶器为例子）')]
    template_keywords = [kw for kw in template_keywords if kw and str(kw) != 'nan']  # 过滤空值

    # 阶段2: 从报告中分割文本
    print("[Step 2/4] 分割报告文本...")
    with open(report_path, 'r', encoding='utf-8') as f:
        full_text = f.read()
    tomb_contents = split_by_tomb(full_text)

    # 阶段3: 对每个墓葬执行自动化抽取
    print("[Step 3/4] 开始自动化提取...")
    all_extracted_data = []
    for tomb_name, text in tomb_contents.items():
        print(f"处理 {tomb_name}...")
        extracted_from_one_tomb = extract_from_text(text, template_keywords)
        for artifact in extracted_from_one_tomb:
            artifact['found_in_tomb'] = tomb_name
        all_extracted_data.extend(extracted_from_one_tomb)

    # 阶段4: 存储到数据库
    print("[Step 4/4] 存储数据到数据库...")
    db = DatabaseManager(db_path)
    db.connect()
    db.create_table()
    for artifact in all_extracted_data:
        db.insert_artifact(artifact)
    db.close()

    print("信息抽取流程已完成。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='从考古报告中提取文物信息。')
    parser.add_argument('-r', '--report', required=True, help='考古报告文件的路径 (e.g., reports/full.md)')
    parser.add_argument('-t', '--template', required=True, help='数据结构模板文件的路径 (e.g., templates/structure_v2.xlsx)')
    parser.add_argument('-d', '--database', default='database/artifacts.db', help='输出数据库文件的路径')
    args = parser.parse_args()
    main(args.report, args.template, args.database)
