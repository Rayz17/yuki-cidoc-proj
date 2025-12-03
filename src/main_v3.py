"""
主程序 V3.0
支持多主体（遗址、时期、陶器、玉器）抽取
"""

import argparse
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.workflow import ExtractionWorkflow


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='考古文物数据抽取系统 V3.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例用法:
  # 抽取玉器和陶器
  python src/main_v3.py \\
    --report "遗址出土报告/瑶山2021修订版解析" \\
    --pottery-template "抽取模版/数据结构1-陶器文化特征单元分析1129.xlsx" \\
    --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx"
  
  # 完整抽取（包含遗址和时期）
  python src/main_v3.py \\
    --report "遗址出土报告/瑶山2021修订版解析" \\
    --site-template "抽取模版/数据结构3-遗址属性和类分析1129.xlsx" \\
    --period-template "抽取模版/数据结构4-时期属性和类分析1129.xlsx" \\
    --pottery-template "抽取模版/数据结构1-陶器文化特征单元分析1129.xlsx" \\
    --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx"
        '''
    )
    
    # 必需参数
    parser.add_argument(
        '--report',
        required=True,
        help='报告文件夹路径（包含full.md和images文件夹）'
    )
    
    # 模板参数
    parser.add_argument(
        '--pottery-template',
        help='陶器抽取模板路径'
    )
    parser.add_argument(
        '--jade-template',
        help='玉器抽取模板路径'
    )
    parser.add_argument(
        '--site-template',
        help='遗址抽取模板路径'
    )
    parser.add_argument(
        '--period-template',
        help='时期抽取模板路径'
    )
    
    # 可选参数
    parser.add_argument(
        '--db',
        default='database/artifacts_v3.db',
        help='数据库路径（默认: database/artifacts_v3.db）'
    )
    parser.add_argument(
        '--report-name',
        help='报告名称（默认使用文件夹名）'
    )
    parser.add_argument(
        '--init-db',
        action='store_true',
        help='初始化数据库（创建表结构）'
    )
    
    args = parser.parse_args()
    
    # 检查报告路径
    if not os.path.exists(args.report):
        print(f"❌ 错误: 报告文件夹不存在: {args.report}")
        return 1
    
    # 检查至少有一个模板
    templates = {}
    if args.pottery_template:
        if not os.path.exists(args.pottery_template):
            print(f"❌ 错误: 陶器模板不存在: {args.pottery_template}")
            return 1
        templates['pottery'] = args.pottery_template
    
    if args.jade_template:
        if not os.path.exists(args.jade_template):
            print(f"❌ 错误: 玉器模板不存在: {args.jade_template}")
            return 1
        templates['jade'] = args.jade_template
    
    if args.site_template:
        if not os.path.exists(args.site_template):
            print(f"❌ 错误: 遗址模板不存在: {args.site_template}")
            return 1
        templates['site'] = args.site_template
    
    if args.period_template:
        if not os.path.exists(args.period_template):
            print(f"❌ 错误: 时期模板不存在: {args.period_template}")
            return 1
        templates['period'] = args.period_template
    
    if not templates:
        print("❌ 错误: 至少需要指定一个模板")
        parser.print_help()
        return 1
    
    # 创建工作流
    print("=" * 60)
    print("考古文物数据抽取系统 V3.0")
    print("=" * 60)
    
    workflow = ExtractionWorkflow(args.db)
    
    try:
        # 初始化数据库
        if args.init_db or not os.path.exists(args.db):
            print("\n📦 初始化数据库...")
            workflow.db.initialize_database()
            print("✅ 数据库初始化完成")
        
        # 显示配置
        print(f"\n📋 抽取配置:")
        print(f"  报告: {args.report}")
        print(f"  数据库: {args.db}")
        print(f"  模板:")
        for entity_type, template_path in templates.items():
            entity_name = {
                'pottery': '陶器',
                'jade': '玉器',
                'site': '遗址',
                'period': '时期'
            }.get(entity_type, entity_type)
            print(f"    - {entity_name}: {os.path.basename(template_path)}")
        
        # 执行抽取
        print(f"\n🚀 开始抽取...")
        print("-" * 60)
        
        task_id = workflow.execute_full_extraction(
            args.report,
            templates,
            args.report_name
        )
        
        print("-" * 60)
        print(f"\n✅ 抽取完成！")
        print(f"   任务ID: {task_id}")
        
        # 显示报告
        print(f"\n📊 抽取报告:")
        report = workflow.get_task_report(task_id)
        
        if report.get('site'):
            print(f"  遗址: {report['site'].get('site_name', '未知')}")
        
        print(f"  陶器: {report['total_pottery']}件", end='')
        if report['pottery_with_images'] > 0:
            print(f" (含图片: {report['pottery_with_images']}件)")
        else:
            print()
        
        print(f"  玉器: {report['total_jade']}件", end='')
        if report['jade_with_images'] > 0:
            print(f" (含图片: {report['jade_with_images']}件)")
        else:
            print()
        
        print(f"  图片: {report['total_images']}张")
        
        print(f"\n💾 数据已保存到: {args.db}")
        print(f"   可使用GUI查看: streamlit run gui/app.py")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 抽取失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        workflow.close()


if __name__ == "__main__":
    sys.exit(main())

