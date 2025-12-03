-- 清理重复图片记录的SQL脚本
-- 使用方法: sqlite3 database/artifacts_v3.db < clean_duplicate_images.sql

-- 1. 查看当前情况
SELECT 
    COUNT(*) as total_records,
    COUNT(DISTINCT image_hash) as unique_images,
    COUNT(*) - COUNT(DISTINCT image_hash) as duplicates
FROM images;

-- 2. 查看重复的图片
SELECT image_hash, COUNT(*) as count 
FROM images 
GROUP BY image_hash 
HAVING count > 1
LIMIT 10;

-- 3. 删除重复记录（保留每个image_hash的第一条记录）
DELETE FROM images 
WHERE id NOT IN (
    SELECT MIN(id) 
    FROM images 
    GROUP BY image_hash
);

-- 4. 验证清理结果
SELECT 
    COUNT(*) as total_records,
    COUNT(DISTINCT image_hash) as unique_images,
    COUNT(*) - COUNT(DISTINCT image_hash) as duplicates
FROM images;

-- 5. 显示清理后的统计
SELECT '清理完成！' as message;
SELECT COUNT(*) as remaining_images FROM images;

