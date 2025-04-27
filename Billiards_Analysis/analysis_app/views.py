import os
import json
import sys
import subprocess
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.urls import reverse

from .forms import BilliardImageForm
from .models import BilliardAnalysis

# 获取项目根目录，用于定位脚本
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print(f"[调试] 项目根目录: {PROJECT_ROOT}")

def index(request):
    """首页视图，显示上传表单"""
    form = BilliardImageForm()
    return render(request, 'analysis_app/index.html', {'form': form})

def analyze_view(request, analysis_id):
    """分析结果展示页面"""
    analysis = get_object_or_404(BilliardAnalysis, id=analysis_id)
    return render(request, 'analysis_app/analysis.html', {'analysis': analysis})

@csrf_exempt
def upload_image(request):
    """处理图片上传，支持表单和AJAX上传"""
    if request.method == 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':  # AJAX请求
            image_file = request.FILES.get('image')
            if not image_file:
                return JsonResponse({'error': '未提供图片文件'}, status=400)
                
            # 创建新的分析记录
            analysis = BilliardAnalysis(image=image_file)
            analysis.save()
            
            # 返回分析ID
            return JsonResponse({
                'success': True,
                'analysis_id': analysis.id,
                'redirect_url': reverse('process_analysis', args=[analysis.id])
            })
        else:  # 普通表单提交
            form = BilliardImageForm(request.POST, request.FILES)
            if form.is_valid():
                analysis = form.save()
                return redirect('process_analysis', analysis_id=analysis.id)
    
    # GET请求或表单无效
    form = BilliardImageForm()
    return render(request, 'analysis_app/index.html', {'form': form})

def process_analysis(request, analysis_id):
    """处理图片分析流程"""
    analysis = get_object_or_404(BilliardAnalysis, id=analysis_id)
    
    try:
        # 获取图片路径
        image_path = analysis.image.path  # 使用.path而不是拼接路径
        print(f"[调试] 图片路径: {image_path}")
        
        # 确保图片存在
        if not os.path.exists(image_path):
            analysis.text_result = "无法找到上传的图片文件。"
            analysis.save()
            return render(request, 'analysis_app/analysis.html', {'analysis': analysis})
        
        # 1. 调用promptFromGPT生成分析数据
        prompt_script = os.path.join(PROJECT_ROOT, "promptFromGPT.py")
        env = os.environ.copy()
        env["BILLIARD_IMAGE_PATH"] = image_path
        
        # 获取当前工作目录（Django项目目录）
        current_dir = os.getcwd()
        print(f"[调试] 当前工作目录: {current_dir}")
        
        prompt_result = run_script(prompt_script, env=env)
        print("[调试] 正在调用promptFromGPT.py脚本...")

        if not prompt_result:
            analysis.text_result = "无法分析图片。请检查图片是否清晰并包含台球。"
            analysis.save()
            return render(request, 'analysis_app/analysis.html', {'analysis': analysis})
        
        # 检查是否生成了billiard_analysis.json文件 (在当前工作目录)
        json_path = os.path.join(current_dir, "billiard_analysis.json")
        print("[调试] 提示生成成功")
        if not os.path.exists(json_path):
            analysis.text_result = "生成分析数据失败。请确保图片包含完整的台球场景。"
            analysis.save()
            return render(request, 'analysis_app/analysis.html', {'analysis': analysis})
            
        # 读取JSON文件
        with open(json_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
            
            # 检查是否包含错误信息
            if "error" in analysis_data:
                print(f"[调试] 分析包含错误信息: {analysis_data['error']}")
                analysis.json_result = analysis_data
                analysis.text_result = analysis_data.get("message", "分析过程中出现错误")
                analysis.save()
                # 返回结果页面，不继续处理检测图片和深度分析
                return render(request, 'analysis_app/analysis.html', {'analysis': analysis})
            
            analysis.json_result = analysis_data
        
        # 只有在成功检测到结果时，才查找和保存检测图片
        if "error" not in analysis.json_result:
            # 查找YOLO检测后的图片
            yolo_runs_dir = os.path.join(PROJECT_ROOT, "yolov5", "runs", "detect")
            print(f"[调试] 查找YOLO检测结果目录: {yolo_runs_dir}")
            
            if os.path.exists(yolo_runs_dir):
                # 获取所有exp开头的目录，按创建时间排序
                exp_dirs = [d for d in os.listdir(yolo_runs_dir) 
                          if d.startswith("exp") and os.path.isdir(os.path.join(yolo_runs_dir, d))]
                
                if exp_dirs:
                    # 按创建时间排序，获取最新的目录
                    latest_exp = max(exp_dirs, key=lambda d: os.path.getctime(os.path.join(yolo_runs_dir, d)))
                    exp_path = os.path.join(yolo_runs_dir, latest_exp)
                    print(f"[调试] 找到最新检测结果目录: {exp_path}")
                    
                    # 获取目录中的图片文件
                    image_files = [f for f in os.listdir(exp_path) 
                                 if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                    
                    if image_files:
                        # 获取最新的图片文件
                        latest_image = max(image_files, key=lambda f: os.path.getctime(os.path.join(exp_path, f)))
                        detected_image_path = os.path.join(exp_path, latest_image)
                        print(f"[调试] 找到检测结果图片: {detected_image_path}")
                        
                        # 将检测图片保存到媒体目录
                        with open(detected_image_path, 'rb') as f:
                            detected_image_content = f.read()
                            # 创建临时文件对象
                            content_file = ContentFile(detected_image_content)
                            # 直接使用models.py中的命名函数
                            analysis.detected_image.save(os.path.basename(detected_image_path), content_file, save=False)
                            
                            print(f"[调试] 已保存检测图片到: {analysis.detected_image.path}")
        
        # 2. 调用Deepseek.py生成分析建议
        deepseek_script = os.path.join(PROJECT_ROOT, "Deepseek.py")
        print("[调试] 正在调用Deepseek.py脚本...")
        deepseek_result = run_script(deepseek_script)
        
        # 检查是否生成了analysis_result.txt文件 (在当前工作目录)
        result_path = os.path.join(current_dir, "analysis_result.txt")
        if os.path.exists(result_path):
            with open(result_path, 'r', encoding='utf-8') as f:
                analysis.text_result = f.read()
        else:
            analysis.text_result = deepseek_result if deepseek_result else "无法获取分析建议"
        
        analysis.save()
        
    except Exception as e:
        analysis.text_result = f"处理过程中发生错误: {str(e)}"
        analysis.save()
    
    return render(request, 'analysis_app/analysis.html', {'analysis': analysis})

def run_script(script_path, env=None):
    """运行Python脚本并获取输出"""
    try:
        # 获取脚本目录
        script_dir = os.path.dirname(script_path)
        print(f"[调试] 脚本路径: {script_dir}")
        
        if env and "BILLIARD_IMAGE_PATH" in env:
            print(f"[调试] 图片路径: {env['BILLIARD_IMAGE_PATH']}")
        
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            encoding='utf-8',
            errors='replace'
        )
        
        stdout, stderr = process.communicate(timeout=180)
        print(f"[调试] 脚本输出: {stdout}")
        print(f"[调试] YOLO输出: {stderr}")
        
        if process.returncode != 0:
            print(f"脚本返回错误码: {process.returncode}")
            return None
            
        return stdout
    except Exception as e:
        print(f"执行脚本错误: {str(e)}")
        return None