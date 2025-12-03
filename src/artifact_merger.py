"""
文物信息合并器
负责合并跨文本块抽取的同一文物信息
"""

import json
from typing import Dict, List, Any, Optional
from collections import defaultdict


class ArtifactMerger:
    """
    文物信息合并器
    合并多个文本块中抽取的同一文物的信息
    """
    
    def __init__(self):
        """初始化合并器"""
        pass
    
    def merge_artifacts(self, 
                       artifact_list: List[Dict],
                       key_field: str = 'artifact_code') -> List[Dict]:
        """
        合并文物列表
        
        Args:
            artifact_list: 文物信息列表
            key_field: 用于识别同一文物的关键字段
        
        Returns:
            合并后的文物列表
        """
        if not artifact_list:
            return []
        
        # 按key_field分组
        grouped = defaultdict(list)
        for artifact in artifact_list:
            key = artifact.get(key_field)
            if key:
                grouped[key].append(artifact)
        
        # 合并每组
        merged = []
        for key, group in grouped.items():
            if len(group) == 1:
                merged.append(group[0])
            else:
                merged_artifact = self._merge_group(group, key_field)
                merged.append(merged_artifact)
        
        return merged
    
    def _merge_group(self, group: List[Dict], key_field: str) -> Dict:
        """
        合并一组文物信息
        
        Args:
            group: 同一文物的多个抽取结果
            key_field: 关键字段
        
        Returns:
            合并后的文物信息
        """
        # 初始化结果
        merged = {}
        
        # 收集所有字段
        all_fields = set()
        for artifact in group:
            all_fields.update(artifact.keys())
        
        # 对每个字段进行合并
        for field in all_fields:
            values = [artifact.get(field) for artifact in group if artifact.get(field) is not None]
            
            if not values:
                merged[field] = None
            elif len(values) == 1:
                merged[field] = values[0]
            else:
                # 多个值，需要合并策略
                merged[field] = self._merge_field_values(field, values)
        
        return merged
    
    def _merge_field_values(self, field_name: str, values: List[Any]) -> Any:
        """
        合并字段值
        
        Args:
            field_name: 字段名
            values: 值列表
        
        Returns:
            合并后的值
        """
        # 去重
        unique_values = []
        for v in values:
            if v not in unique_values:
                unique_values.append(v)
        
        if len(unique_values) == 1:
            return unique_values[0]
        
        # 数值类型：取最精确的（最长的字符串表示或最大的数值）
        if all(isinstance(v, (int, float)) for v in unique_values):
            return max(unique_values)
        
        # 文本类型：取最长的
        if all(isinstance(v, str) for v in unique_values):
            # 特殊处理：如果是描述性字段，合并所有信息
            if any(keyword in field_name.lower() for keyword in 
                   ['description', 'features', 'characteristics', '特征', '描述', '说明']):
                return ' | '.join(unique_values)
            else:
                # 其他字段取最长的
                return max(unique_values, key=len)
        
        # 混合类型：转为字符串后合并
        return ' | '.join(str(v) for v in unique_values)
    
    def merge_with_confidence(self,
                             artifact_list: List[Dict],
                             key_field: str = 'artifact_code') -> List[Dict]:
        """
        带置信度的合并
        
        Args:
            artifact_list: 文物信息列表（每个包含confidence字段）
            key_field: 关键字段
        
        Returns:
            合并后的文物列表
        """
        if not artifact_list:
            return []
        
        # 按key_field分组
        grouped = defaultdict(list)
        for artifact in artifact_list:
            key = artifact.get(key_field)
            if key:
                grouped[key].append(artifact)
        
        # 合并每组
        merged = []
        for key, group in grouped.items():
            if len(group) == 1:
                merged.append(group[0])
            else:
                merged_artifact = self._merge_group_with_confidence(group, key_field)
                merged.append(merged_artifact)
        
        return merged
    
    def _merge_group_with_confidence(self, group: List[Dict], key_field: str) -> Dict:
        """
        带置信度的合并一组
        
        Args:
            group: 同一文物的多个抽取结果
            key_field: 关键字段
        
        Returns:
            合并后的文物信息
        """
        # 初始化结果
        merged = {}
        
        # 收集所有字段
        all_fields = set()
        for artifact in group:
            all_fields.update(artifact.keys())
        
        # 对每个字段进行合并
        for field in all_fields:
            if field == 'extraction_confidence':
                # 置信度取平均
                confidences = [artifact.get(field, 0) for artifact in group]
                merged[field] = sum(confidences) / len(confidences)
            else:
                # 其他字段：优先选择置信度高的
                field_values = []
                for artifact in group:
                    if field in artifact and artifact[field] is not None:
                        confidence = artifact.get('extraction_confidence', 0.5)
                        field_values.append((artifact[field], confidence))
                
                if not field_values:
                    merged[field] = None
                elif len(field_values) == 1:
                    merged[field] = field_values[0][0]
                else:
                    # 选择置信度最高的
                    merged[field] = max(field_values, key=lambda x: x[1])[0]
        
        return merged
    
    def detect_conflicts(self, artifact_list: List[Dict], key_field: str = 'artifact_code') -> List[Dict]:
        """
        检测冲突
        
        Args:
            artifact_list: 文物信息列表
            key_field: 关键字段
        
        Returns:
            冲突报告列表
        """
        conflicts = []
        
        # 按key_field分组
        grouped = defaultdict(list)
        for artifact in artifact_list:
            key = artifact.get(key_field)
            if key:
                grouped[key].append(artifact)
        
        # 检查每组的冲突
        for key, group in grouped.items():
            if len(group) > 1:
                group_conflicts = self._detect_group_conflicts(key, group)
                if group_conflicts:
                    conflicts.append({
                        'artifact_code': key,
                        'conflicts': group_conflicts
                    })
        
        return conflicts
    
    def _detect_group_conflicts(self, key: str, group: List[Dict]) -> List[Dict]:
        """
        检测一组内的冲突
        
        Args:
            key: 文物编号
            group: 同一文物的多个抽取结果
        
        Returns:
            冲突列表
        """
        conflicts = []
        
        # 收集所有字段
        all_fields = set()
        for artifact in group:
            all_fields.update(artifact.keys())
        
        # 检查每个字段
        for field in all_fields:
            values = [artifact.get(field) for artifact in group if artifact.get(field) is not None]
            
            if len(values) > 1:
                unique_values = list(set(str(v) for v in values))
                if len(unique_values) > 1:
                    conflicts.append({
                        'field': field,
                        'values': values,
                        'count': len(values)
                    })
        
        return conflicts
    
    def merge_by_similarity(self,
                           artifact_list: List[Dict],
                           similarity_threshold: float = 0.8) -> List[Dict]:
        """
        基于相似度的合并（用于没有明确编号的情况）
        
        Args:
            artifact_list: 文物信息列表
            similarity_threshold: 相似度阈值
        
        Returns:
            合并后的文物列表
        """
        if not artifact_list:
            return []
        
        # 构建相似度矩阵
        n = len(artifact_list)
        similarity_matrix = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._calculate_similarity(artifact_list[i], artifact_list[j])
                similarity_matrix[i][j] = sim
                similarity_matrix[j][i] = sim
        
        # 聚类
        clusters = []
        used = set()
        
        for i in range(n):
            if i in used:
                continue
            
            cluster = [i]
            used.add(i)
            
            for j in range(i + 1, n):
                if j not in used and similarity_matrix[i][j] >= similarity_threshold:
                    cluster.append(j)
                    used.add(j)
            
            clusters.append(cluster)
        
        # 合并每个聚类
        merged = []
        for cluster in clusters:
            group = [artifact_list[i] for i in cluster]
            if len(group) == 1:
                merged.append(group[0])
            else:
                merged_artifact = self._merge_group(group, 'artifact_code')
                merged.append(merged_artifact)
        
        return merged
    
    def _calculate_similarity(self, artifact1: Dict, artifact2: Dict) -> float:
        """
        计算两个文物的相似度
        
        Args:
            artifact1: 文物1
            artifact2: 文物2
        
        Returns:
            相似度 (0-1)
        """
        # 获取所有字段
        fields1 = set(artifact1.keys())
        fields2 = set(artifact2.keys())
        all_fields = fields1 | fields2
        
        if not all_fields:
            return 0.0
        
        # 计算匹配字段数
        matches = 0
        total = 0
        
        for field in all_fields:
            if field in artifact1 and field in artifact2:
                total += 1
                v1 = artifact1[field]
                v2 = artifact2[field]
                
                if v1 == v2:
                    matches += 1
                elif isinstance(v1, str) and isinstance(v2, str):
                    # 文本相似度（简单版本）
                    if v1 in v2 or v2 in v1:
                        matches += 0.5
        
        return matches / total if total > 0 else 0.0
    
    def get_merge_statistics(self, 
                            original_list: List[Dict],
                            merged_list: List[Dict]) -> Dict:
        """
        获取合并统计信息
        
        Args:
            original_list: 原始列表
            merged_list: 合并后列表
        
        Returns:
            统计信息
        """
        return {
            'original_count': len(original_list),
            'merged_count': len(merged_list),
            'reduction': len(original_list) - len(merged_list),
            'reduction_rate': (len(original_list) - len(merged_list)) / len(original_list) if original_list else 0
        }


# 示例用法
if __name__ == "__main__":
    merger = ArtifactMerger()
    
    # 测试数据
    test_artifacts = [
        {
            'artifact_code': 'M12:1',
            'subtype': '罐',
            'color': '红',
            'extraction_confidence': 0.9
        },
        {
            'artifact_code': 'M12:1',
            'height': 15,
            'diameter': 12,
            'clay_type': '夹砂陶',
            'extraction_confidence': 0.85
        },
        {
            'artifact_code': 'M12:2',
            'subtype': '钵',
            'color': '灰',
            'extraction_confidence': 0.95
        },
        {
            'artifact_code': 'M12:1',
            'color': '红褐',
            'dimensions': '口径12cm，高15cm',
            'extraction_confidence': 0.8
        }
    ]
    
    print("=" * 60)
    print("原始数据:")
    print("=" * 60)
    for i, art in enumerate(test_artifacts, 1):
        print(f"{i}. {art}")
    
    # 检测冲突
    print("\n" + "=" * 60)
    print("冲突检测:")
    print("=" * 60)
    conflicts = merger.detect_conflicts(test_artifacts)
    for conflict in conflicts:
        print(f"\n文物 {conflict['artifact_code']} 存在冲突:")
        for c in conflict['conflicts']:
            print(f"  字段 '{c['field']}' 有 {c['count']} 个不同值: {c['values']}")
    
    # 简单合并
    print("\n" + "=" * 60)
    print("简单合并结果:")
    print("=" * 60)
    merged_simple = merger.merge_artifacts(test_artifacts)
    for i, art in enumerate(merged_simple, 1):
        print(f"\n{i}. {json.dumps(art, ensure_ascii=False, indent=2)}")
    
    # 带置信度合并
    print("\n" + "=" * 60)
    print("带置信度合并结果:")
    print("=" * 60)
    merged_conf = merger.merge_with_confidence(test_artifacts)
    for i, art in enumerate(merged_conf, 1):
        print(f"\n{i}. {json.dumps(art, ensure_ascii=False, indent=2)}")
    
    # 统计
    print("\n" + "=" * 60)
    print("合并统计:")
    print("=" * 60)
    stats = merger.get_merge_statistics(test_artifacts, merged_simple)
    print(f"原始数量: {stats['original_count']}")
    print(f"合并后数量: {stats['merged_count']}")
    print(f"减少数量: {stats['reduction']}")
    print(f"减少比例: {stats['reduction_rate']:.1%}")
    
    print("\n✅ 文物合并器测试完成")

