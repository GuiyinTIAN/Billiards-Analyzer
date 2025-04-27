from django.db import models
import uuid
import os

def image_upload_path(instance, filename):
    # 生成唯一文件名，避免覆盖
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('uploads', filename)

def detected_image_path(instance, filename):
    # 为检测结果图片生成唯一文件名，保存到detect文件夹
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('detect', filename)

class BilliardAnalysis(models.Model):
    image = models.ImageField(upload_to=image_upload_path, verbose_name="台球图片")
    detected_image = models.ImageField(upload_to=detected_image_path, null=True, blank=True, verbose_name="检测结果图片")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    json_result = models.JSONField(null=True, blank=True, verbose_name="分析JSON")
    text_result = models.TextField(null=True, blank=True, verbose_name="分析结论")
    
    class Meta:
        verbose_name = "台球分析"
        verbose_name_plural = "台球分析"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"分析 ID:{self.id} - 创建于:{self.created_at.strftime('%Y-%m-%d %H:%M')}"
