"""
图片关联器
负责将文物与图片进行智能关联
"""

import re
import json
import sys
import os
from typing import Dict, List, Optional, Tuple

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.image_manager import ImageManager


class ImageLinker:
    """
    图片关联器
    根据文物编号、描述等信息，智能关联图片
    """
    
    def __init__(self, image_manager: ImageManager):
        """
        初始化图片关联器
        
        Args:
            image_manager: 图片管理器实例
        """
        self.image_manager = image_manager
    
    def link_artifact_to_images(self,
                               artifact: Dict,
                               artifact_type: str) -> List[Dict]:
        """
        为文物关联图片
        
        Args:
            artifact: 文物信息
            artifact_type: 文物类型 (pottery/jade)
        
        Returns:
            关联的图片列表
        """
        artifact_code = artifact.get('artifact_code', '')
        
        if not artifact_code:
            return []
        
        # 策略1: 通过文物编号精确匹配
        images_by_code = self._find_images_by_artifact_code(artifact_code)
        
        # 策略2: 通过文本内容匹配
        images_by_text = self._find_images_by_text_content(artifact)
        
        # 策略3: 通过墓葬编号匹配
        images_by_tomb = self._find_images_by_tomb(artifact_code)
        
        # 策略4: 通过显式引用匹配 (e.g. "见图一")
        images_by_ref = self._find_images_by_explicit_reference(artifact_code)
        
        # 策略5: 通过LLM提取的引用匹配 (V3.8)
        images_by_llm = self._find_images_by_llm_references(artifact)
        
        # 合并结果并去重
        all_images = self._merge_and_deduplicate([
            images_by_llm, # 优先级最高
            images_by_ref,
            images_by_code,
            images_by_text,
            images_by_tomb
        ])
        
        # 为每张图片分配角色
        linked_images = []
        for i, img in enumerate(all_images):
            linked_images.append({
                'image_hash': img['image_hash'],
                'image_path': img.get('image_path', ''),
                'image_role': self._determine_image_role(img, artifact_code, i),
                'confidence': img.get('confidence', 0.5),
                'display_order': i,
                'page_idx': img.get('page_idx'),
                'caption': img.get('caption', '')
            })
        
        return linked_images
    
    def _find_images_by_llm_references(self, artifact: Dict) -> List[Dict]:
        """
        通过LLM提取的图片引用查找图片 (V3.8)
        """
        refs = artifact.get('image_references', [])
        if not refs or not isinstance(refs, list):
            return []
            
        if not self.image_manager.content_list:
            return []
            
        images = []
        
        # 遍历LLM提取的所有引用 (e.g. "图一", "图版二:1")
        for ref in refs:
            ref_str = str(ref).strip()
            if not ref_str: continue
            
            # 尝试匹配图片
            for item in self.image_manager.content_list:
                if item.get('type') == 'image':
                    image_hash = self.image_manager._extract_hash_from_item(item)
                    caption = self.image_manager.extract_image_caption(image_hash)
                    
                    is_match = False
                    # 1. 检查文件名
                    if image_hash and ref_str in image_hash:
                        is_match = True
                    # 2. 检查Caption
                    elif caption and (caption.startswith(ref_str) or f" {ref_str} " in caption):
                        is_match = True
                    
                    if is_match:
                        images.append({
                            'image_hash': image_hash,
                            'page_idx': item.get('page_idx'),
                            'bbox': item.get('bbox', []),
                            'caption': caption,
                            'confidence': 0.98, # LLM提取的引用，置信度极高
                            'match_method': 'llm_reference'
                        })
                        
        return images

    def _find_images_by_explicit_reference(self, artifact_code: str) -> List[Dict]:
        """
        通过文本中的显式引用查找图片 (如"见图一")
        """
        if not self.image_manager.content_list:
            return []
            
        images = []
        found_refs = set()
        
        # 1. 找到包含 artifact_code 的文本段落
        for item in self.image_manager.content_list:
            if item.get('type') == 'text':
                text = item.get('text', '')
                if artifact_code in text:
                    # 2. 提取引用 (图一、图1、图版二、Figure 3)
                    # 匹配模式: (图|图版|Fig\.?|Figure)\s*([一二三四五六七八九十\d]+)
                    refs = re.findall(r'(图|图版|Fig\.?|Figure)\s*([一二三四五六七八九十\d]+)', text)
                    for prefix, num in refs:
                        found_refs.add(f"{prefix}{num}")
                        # 同时也添加纯数字版本以便模糊匹配
                        found_refs.add(str(num))
        
        if not found_refs:
            return []
            
        # 3. 查找匹配的图片 (检查文件名或Caption)
        for item in self.image_manager.content_list:
            if item.get('type') == 'image':
                image_hash = self.image_manager._extract_hash_from_item(item) # 通常是文件名
                caption = self.image_manager.extract_image_caption(image_hash)
                
                is_match = False
                for ref in found_refs:
                    # 检查文件名是否包含引用
                    if image_hash and ref in image_hash:
                        is_match = True
                    # 检查Caption是否包含引用 (需要是开头或明确的标识)
                    elif caption and (caption.startswith(ref) or f" {ref} " in caption):
                        is_match = True
                        
                if is_match:
                    images.append({
                        'image_hash': image_hash,
                        'page_idx': item.get('page_idx'),
                        'bbox': item.get('bbox', []),
                        'caption': caption,
                        'confidence': 0.95, # 非常高的置信度
                        'match_method': 'explicit_reference'
                    })
                    
        return images

    def _find_images_by_artifact_code(self, artifact_code: str) -> List[Dict]:
        """
        通过文物编号查找图片
        
        Args:
            artifact_code: 文物编号（如M12:1）
        
        Returns:
            图片列表
        """
        if not self.image_manager.content_list:
            return []
        
        images = []
        
        # 在content_list中查找包含文物编号的文本
        for i, item in enumerate(self.image_manager.content_list):
            if item.get('type') == 'text':
                text = item.get('text', '')
                
                # 检查文本中是否包含文物编号
                if artifact_code in text or self._normalize_code(artifact_code) in self._normalize_code(text):
                    # 查找附近的图片
                    nearby_images = self._find_nearby_images(i, distance=5)
                    for img in nearby_images:
                        img['confidence'] = 0.9  # 高置信度
                        img['match_method'] = 'artifact_code'
                    images.extend(nearby_images)
        
        return images
    
    def _find_images_by_text_content(self, artifact: Dict) -> List[Dict]:
        """
        通过文物描述查找图片
        
        Args:
            artifact: 文物信息
        
        Returns:
            图片列表
        """
        if not self.image_manager.content_list:
            return []
        
        # 提取关键描述词
        keywords = self._extract_keywords(artifact)
        
        if not keywords:
            return []
        
        images = []
        
        # 在content_list中查找包含关键词的文本
        for i, item in enumerate(self.image_manager.content_list):
            if item.get('type') == 'text':
                text = item.get('text', '')
                
                # 检查是否包含多个关键词
                match_count = sum(1 for kw in keywords if kw in text)
                if match_count >= 2:  # 至少匹配2个关键词
                    nearby_images = self._find_nearby_images(i, distance=3)
                    for img in nearby_images:
                        img['confidence'] = 0.6 + (match_count * 0.1)  # 根据匹配数量调整置信度
                        img['match_method'] = 'text_content'
                    images.extend(nearby_images)
        
        return images
    
    def _find_images_by_tomb(self, artifact_code: str) -> List[Dict]:
        """
        通过墓葬编号查找图片
        
        Args:
            artifact_code: 文物编号（如M12:1）
        
        Returns:
            图片列表
        """
        # 提取墓葬编号
        tomb_code = self._extract_tomb_code(artifact_code)
        
        if not tomb_code or not self.image_manager.content_list:
            return []
        
        images = []
        
        # 查找墓葬相关的图片
        for i, item in enumerate(self.image_manager.content_list):
            if item.get('type') == 'text':
                text = item.get('text', '')
                
                # 检查是否是墓葬标题或描述
                if tomb_code in text and any(keyword in text for keyword in ['墓', '墓葬', 'M']):
                    nearby_images = self._find_nearby_images(i, distance=10)
                    for img in nearby_images:
                        img['confidence'] = 0.4  # 较低置信度
                        img['match_method'] = 'tomb_context'
                    images.extend(nearby_images)
        
        return images
    
    def _find_nearby_images(self, text_index: int, distance: int = 5) -> List[Dict]:
        """
        查找文本项附近的图片
        
        Args:
            text_index: 文本项索引
            distance: 查找距离
        
        Returns:
            附近的图片列表
        """
        if not self.image_manager.content_list:
            return []
        
        images = []
        start = max(0, text_index - distance)
        end = min(len(self.image_manager.content_list), text_index + distance + 1)
        
        for i in range(start, end):
            item = self.image_manager.content_list[i]
            if item.get('type') == 'image':
                image_hash = self.image_manager._extract_hash_from_item(item)
                if image_hash:
                    images.append({
                        'image_hash': image_hash,
                        'page_idx': item.get('page_idx'),
                        'bbox': item.get('bbox', []),
                        'caption': self.image_manager.extract_image_caption(image_hash),
                        'distance_from_text': abs(i - text_index)
                    })
        
        return images
    
    def _extract_keywords(self, artifact: Dict) -> List[str]:
        """
        从文物信息中提取关键词
        
        Args:
            artifact: 文物信息
        
        Returns:
            关键词列表
        """
        keywords = []
        
        # 关键字段
        key_fields = ['subtype', 'category_level1', 'category_level2', 
                     'jade_type', 'clay_type', 'shape_unit', 'decoration_unit']
        
        for field in key_fields:
            value = artifact.get(field)
            if value and isinstance(value, str) and len(value) > 1:
                keywords.append(value)
        
        # 从artifact_code提取
        artifact_code = artifact.get('artifact_code', '')
        if artifact_code:
            keywords.append(artifact_code)
        
        return keywords
    
    def _extract_tomb_code(self, artifact_code: str) -> Optional[str]:
        """
        从文物编号中提取墓葬编号
        
        Args:
            artifact_code: 文物编号（如M12:1）
        
        Returns:
            墓葬编号（如M12）
        """
        # 匹配模式: M12:1 -> M12
        match = re.match(r'(M\d+)', artifact_code)
        if match:
            return match.group(1)
        
        return None
    
    def _normalize_code(self, text: str) -> str:
        """
        标准化编号格式
        
        Args:
            text: 文本
        
        Returns:
            标准化后的文本
        """
        # 移除空格和特殊字符
        text = re.sub(r'[\s\-_]', '', text)
        # 统一冒号
        text = text.replace('：', ':')
        return text
    
    def _determine_image_role(self, image: Dict, artifact_code: str, index: int) -> str:
        """
        确定图片角色
        
        Args:
            image: 图片信息
            artifact_code: 文物编号
            index: 图片索引
        
        Returns:
            图片角色 (photo/drawing/diagram/context)
        """
        caption = image.get('caption', '').lower()
        
        # 根据说明文字判断
        if '照片' in caption or 'photo' in caption:
            return 'photo'
        elif '图' in caption or '线图' in caption or 'drawing' in caption:
            return 'drawing'
        elif '示意' in caption or 'diagram' in caption:
            return 'diagram'
        elif '位置' in caption or 'context' in caption or '墓' in caption:
            return 'context'
        
        # 根据匹配方法判断
        match_method = image.get('match_method', '')
        if match_method in ['llm_reference', 'explicit_reference']:
            return 'photo' # 显式引用通常是照片或线图，默认为重要图片
        elif match_method == 'artifact_code':
            return 'photo' if index == 0 else 'drawing'
        elif match_method == 'tomb_context':
            return 'context'
        
        # 默认
        return 'photo' if index == 0 else 'related'
    
    def _merge_and_deduplicate(self, image_lists: List[List[Dict]]) -> List[Dict]:
        """
        合并并去重图片列表
        
        Args:
            image_lists: 多个图片列表
        
        Returns:
            合并去重后的列表
        """
        seen = set()
        merged = []
        
        for image_list in image_lists:
            for image in image_list:
                image_hash = image.get('image_hash')
                if image_hash and image_hash not in seen:
                    seen.add(image_hash)
                    merged.append(image)
        
        # 按置信度和距离排序
        merged.sort(key=lambda x: (
            -x.get('confidence', 0),
            x.get('distance_from_text', 999)
        ))
        
        return merged
    
    def batch_link_artifacts(self,
                            artifacts: List[Dict],
                            artifact_type: str) -> Dict[str, List[Dict]]:
        """
        批量关联文物与图片
        
        Args:
            artifacts: 文物列表
            artifact_type: 文物类型
        
        Returns:
            文物编号到图片列表的映射
        """
        results = {}
        
        for artifact in artifacts:
            artifact_code = artifact.get('artifact_code')
            if artifact_code:
                images = self.link_artifact_to_images(artifact, artifact_type)
                results[artifact_code] = images
        
        return results
    
    def get_linking_statistics(self, linking_results: Dict[str, List[Dict]]) -> Dict:
        """
        获取关联统计信息
        
        Args:
            linking_results: 关联结果
        
        Returns:
            统计信息
        """
        total_artifacts = len(linking_results)
        artifacts_with_images = sum(1 for images in linking_results.values() if images)
        total_images = sum(len(images) for images in linking_results.values())
        
        return {
            'total_artifacts': total_artifacts,
            'artifacts_with_images': artifacts_with_images,
            'artifacts_without_images': total_artifacts - artifacts_with_images,
            'total_images_linked': total_images,
            'avg_images_per_artifact': total_images / total_artifacts if total_artifacts > 0 else 0,
            'linking_rate': artifacts_with_images / total_artifacts if total_artifacts > 0 else 0
        }


# 示例用法
if __name__ == "__main__":
    import os
    
    # 测试
    report_path = "遗址出土报告/瑶山2021修订版解析"
    
    if os.path.exists(report_path):
        # 创建图片管理器
        img_manager = ImageManager(report_path)
        
        # 创建图片关联器
        linker = ImageLinker(img_manager)
        
        # 测试文物
        test_artifacts = [
            {
                'artifact_code': 'M12:1',
                'subtype': '玉琮',
                'jade_type': '透闪石玉',
                'category_level1': '玉礼器'
            },
            {
                'artifact_code': 'M12:2',
                'subtype': '玉璧',
                'jade_type': '透闪石玉'
            }
        ]
        
        print("=" * 60)
        print("测试图片关联")
        print("=" * 60)
        
        for artifact in test_artifacts:
            print(f"\n文物: {artifact['artifact_code']} - {artifact.get('subtype', '未知')}")
            images = linker.link_artifact_to_images(artifact, 'jade')
            print(f"  关联到 {len(images)} 张图片")
            for img in images[:3]:  # 只显示前3张
                print(f"    - {img['image_hash'][:16]}... "
                      f"(角色: {img['image_role']}, 置信度: {img['confidence']:.2f})")
        
        # 批量关联
        print("\n" + "=" * 60)
        print("批量关联测试")
        print("=" * 60)
        results = linker.batch_link_artifacts(test_artifacts, 'jade')
        stats = linker.get_linking_statistics(results)
        
        print(f"总文物数: {stats['total_artifacts']}")
        print(f"有图片的文物: {stats['artifacts_with_images']}")
        print(f"总关联图片数: {stats['total_images_linked']}")
        print(f"平均每文物图片数: {stats['avg_images_per_artifact']:.1f}")
        print(f"关联成功率: {stats['linking_rate']:.1%}")
        
        print("\n✅ 图片关联器测试完成")
    else:
        print(f"⚠️  报告路径不存在: {report_path}")

