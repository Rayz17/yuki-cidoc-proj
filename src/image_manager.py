"""
图片管理器
负责索引报告中的所有图片，提取元数据
"""

import os
import json
from PIL import Image
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class ImageManager:
    """
    图片管理器
    索引报告中的所有图片并提取元数据
    """
    
    def __init__(self, report_folder_path: str):
        """
        初始化图片管理器
        
        Args:
            report_folder_path: 报告文件夹路径
        """
        self.report_folder_path = report_folder_path
        self.images_folder = os.path.join(report_folder_path, 'images')
        self.content_list_path = self._find_content_list_json()
        self.content_list = None
        
        if self.content_list_path:
            self._load_content_list()
    
    def _find_content_list_json(self) -> Optional[str]:
        """查找content_list.json文件"""
        for file in os.listdir(self.report_folder_path):
            if file.endswith('_content_list.json'):
                return os.path.join(self.report_folder_path, file)
        return None
    
    def _load_content_list(self):
        """加载content_list.json"""
        if self.content_list_path and os.path.exists(self.content_list_path):
            with open(self.content_list_path, 'r', encoding='utf-8') as f:
                self.content_list = json.load(f)
            print(f"✅ 已加载 content_list.json，共 {len(self.content_list)} 项")
    
    def index_all_images(self) -> List[Dict]:
        """
        索引所有图片
        
        Returns:
            图片信息列表
        """
        if not os.path.exists(self.images_folder):
            print(f"⚠️  图片文件夹不存在: {self.images_folder}")
            return []
        
        image_files = [f for f in os.listdir(self.images_folder) 
                      if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        
        print(f"📸 开始索引 {len(image_files)} 张图片...")
        
        images_data = []
        for i, image_file in enumerate(image_files, 1):
            if i % 100 == 0:
                print(f"  进度: {i}/{len(image_files)}")
            
            image_path = os.path.join(self.images_folder, image_file)
            image_hash = os.path.splitext(image_file)[0]
            
            # 提取图片元数据
            image_data = self._extract_image_metadata(image_path, image_hash)
            
            # 从content_list中获取额外信息
            if self.content_list:
                content_info = self._find_image_in_content_list(image_hash)
                if content_info:
                    image_data.update(content_info)
            
            images_data.append(image_data)
        
        print(f"✅ 图片索引完成，共 {len(images_data)} 张")
        return images_data
    
    def _extract_image_metadata(self, image_path: str, image_hash: str) -> Dict:
        """
        提取图片元数据
        
        Args:
            image_path: 图片路径
            image_hash: 图片哈希值
        
        Returns:
            图片元数据字典
        """
        metadata = {
            'image_hash': image_hash,
            'image_path': image_path,
            'file_size': os.path.getsize(image_path),
            'width': None,
            'height': None
        }
        
        try:
            with Image.open(image_path) as img:
                metadata['width'] = img.width
                metadata['height'] = img.height
        except Exception as e:
            print(f"⚠️  无法读取图片 {image_hash}: {e}")
        
        return metadata
    
    def _find_image_in_content_list(self, image_hash: str) -> Optional[Dict]:
        """
        在content_list中查找图片信息
        
        Args:
            image_hash: 图片哈希值
        
        Returns:
            图片在content_list中的信息
        """
        if not self.content_list:
            return None
        
        for item in self.content_list:
            if item.get('type') == 'image':
                # 尝试从不同字段提取图片哈希
                item_hash = self._extract_hash_from_item(item)
                if item_hash == image_hash:
                    return {
                        'page_idx': item.get('page_idx'),
                        'bbox': json.dumps(item.get('bbox', [])),
                        'related_text': self._extract_nearby_text(item)
                    }
        
        return None
    
    def _extract_hash_from_item(self, item: Dict) -> Optional[str]:
        """从content_list项中提取图片哈希"""
        # 尝试不同的字段
        for field in ['image_hash', 'hash', 'id', 'path']:
            if field in item:
                value = item[field]
                if isinstance(value, str):
                    # 如果是路径，提取文件名
                    if '/' in value or '\\' in value:
                        value = os.path.splitext(os.path.basename(value))[0]
                    return value
        return None
    
    def _extract_nearby_text(self, image_item: Dict, distance: int = 3) -> str:
        """
        提取图片附近的文本（作为图片说明）
        
        Args:
            image_item: 图片项
            distance: 查找距离（前后几项）
        
        Returns:
            附近的文本内容
        """
        if not self.content_list:
            return ''
        
        try:
            idx = self.content_list.index(image_item)
            
            # 查找前后的文本项
            nearby_texts = []
            for i in range(max(0, idx - distance), min(len(self.content_list), idx + distance + 1)):
                item = self.content_list[i]
                if item.get('type') == 'text' and item.get('text'):
                    nearby_texts.append(item['text'])
            
            return ' '.join(nearby_texts)[:500]  # 限制长度
        except (ValueError, IndexError):
            return ''
    
    def find_images_by_page(self, page_idx: int) -> List[Dict]:
        """
        查找指定页码的所有图片
        
        Args:
            page_idx: 页码
        
        Returns:
            图片列表
        """
        if not self.content_list:
            return []
        
        images = []
        for item in self.content_list:
            if item.get('type') == 'image' and item.get('page_idx') == page_idx:
                image_hash = self._extract_hash_from_item(item)
                if image_hash:
                    images.append({
                        'image_hash': image_hash,
                        'page_idx': page_idx,
                        'bbox': item.get('bbox', [])
                    })
        
        return images
    
    def find_images_near_text(self, text_content: str, max_distance: int = 500) -> List[Dict]:
        """
        查找文本附近的图片
        
        Args:
            text_content: 文本内容
            max_distance: 最大距离（像素）
        
        Returns:
            附近的图片列表
        """
        if not self.content_list:
            return []
        
        # 找到包含该文本的项
        text_items = [item for item in self.content_list 
                     if item.get('type') == 'text' and text_content in item.get('text', '')]
        
        if not text_items:
            return []
        
        nearby_images = []
        for text_item in text_items:
            text_bbox = text_item.get('bbox', [])
            text_page = text_item.get('page_idx')
            
            if not text_bbox or text_page is None:
                continue
            
            # 查找同页或相邻页的图片
            for item in self.content_list:
                if item.get('type') == 'image':
                    img_page = item.get('page_idx')
                    img_bbox = item.get('bbox', [])
                    
                    # 同页或相邻页
                    if img_page is not None and abs(img_page - text_page) <= 1:
                        # 计算距离
                        if img_bbox and len(img_bbox) >= 4 and len(text_bbox) >= 4:
                            distance = self._calculate_bbox_distance(text_bbox, img_bbox)
                            if distance <= max_distance:
                                image_hash = self._extract_hash_from_item(item)
                                if image_hash:
                                    nearby_images.append({
                                        'image_hash': image_hash,
                                        'page_idx': img_page,
                                        'distance': distance,
                                        'bbox': img_bbox
                                    })
        
        # 按距离排序
        nearby_images.sort(key=lambda x: x['distance'])
        return nearby_images
    
    def _calculate_bbox_distance(self, bbox1: List, bbox2: List) -> float:
        """
        计算两个边界框的距离
        
        Args:
            bbox1: 边界框1 [x1, y1, x2, y2]
            bbox2: 边界框2 [x1, y1, x2, y2]
        
        Returns:
            距离（像素）
        """
        # 计算中心点
        center1 = [(bbox1[0] + bbox1[2]) / 2, (bbox1[1] + bbox1[3]) / 2]
        center2 = [(bbox2[0] + bbox2[2]) / 2, (bbox2[1] + bbox2[3]) / 2]
        
        # 欧几里得距离
        distance = ((center1[0] - center2[0]) ** 2 + (center1[1] - center2[1]) ** 2) ** 0.5
        return distance
    
    def extract_image_caption(self, image_hash: str) -> str:
        """
        提取图片说明
        
        Args:
            image_hash: 图片哈希值
        
        Returns:
            图片说明文本
        """
        if not self.content_list:
            return ''
        
        # 找到图片项
        for i, item in enumerate(self.content_list):
            if item.get('type') == 'image':
                item_hash = self._extract_hash_from_item(item)
                if item_hash == image_hash:
                    # 查找图片后的第一个文本项（通常是图片说明）
                    for j in range(i + 1, min(i + 5, len(self.content_list))):
                        next_item = self.content_list[j]
                        if next_item.get('type') == 'text':
                            text = next_item.get('text', '').strip()
                            # 如果文本以"图"、"Fig"等开头，很可能是图片说明
                            if text and (text.startswith('图') or 
                                       text.startswith('Fig') or 
                                       text.startswith('图版')):
                                return text
                    
                    # 如果没找到明确的图片说明，返回附近文本
                    return self._extract_nearby_text(item, distance=2)
        
        return ''
    
    def get_statistics(self) -> Dict:
        """
        获取图片统计信息
        
        Returns:
            统计信息字典
        """
        if not os.path.exists(self.images_folder):
            return {'total': 0}
        
        image_files = [f for f in os.listdir(self.images_folder) 
                      if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        
        total_size = sum(os.path.getsize(os.path.join(self.images_folder, f)) 
                        for f in image_files)
        
        return {
            'total': len(image_files),
            'total_size_mb': total_size / (1024 * 1024),
            'images_folder': self.images_folder,
            'has_content_list': self.content_list is not None
        }


# 示例用法
if __name__ == "__main__":
    # 测试
    report_path = "遗址出土报告/瑶山2021修订版解析"
    
    if os.path.exists(report_path):
        manager = ImageManager(report_path)
        
        # 获取统计信息
        stats = manager.get_statistics()
        print(f"\n图片统计:")
        print(f"  总数: {stats['total']}")
        print(f"  总大小: {stats['total_size_mb']:.2f} MB")
        print(f"  有content_list: {stats['has_content_list']}")
        
        # 索引前10张图片作为测试
        print(f"\n测试索引前10张图片...")
        images_folder = os.path.join(report_path, 'images')
        test_files = [f for f in os.listdir(images_folder) 
                     if f.lower().endswith('.jpg')][:10]
        
        for img_file in test_files:
            img_hash = os.path.splitext(img_file)[0]
            img_path = os.path.join(images_folder, img_file)
            metadata = manager._extract_image_metadata(img_path, img_hash)
            print(f"  {img_file}: {metadata['width']}x{metadata['height']}, "
                  f"{metadata['file_size']/1024:.1f}KB")
        
        print("\n✅ 图片管理器测试完成")
    else:
        print(f"⚠️  报告路径不存在: {report_path}")

