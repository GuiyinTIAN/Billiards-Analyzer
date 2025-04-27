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

# Get project root directory for locating scripts
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print(f"[Debug] Project root directory: {PROJECT_ROOT}")

def index(request):
    """Home view, displays upload form"""
    form = BilliardImageForm()
    return render(request, 'analysis_app/index.html', {'form': form})

def analyze_view(request, analysis_id):
    """Analysis result display page"""
    analysis = get_object_or_404(BilliardAnalysis, id=analysis_id)
    return render(request, 'analysis_app/analysis.html', {'analysis': analysis})

@csrf_exempt
def upload_image(request):
    """Handle image upload, supports form and AJAX upload"""
    if request.method == 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':  # AJAX request
            image_file = request.FILES.get('image')
            if not image_file:
                return JsonResponse({'error': 'No image file provided'}, status=400)
                
            # Create new analysis record
            analysis = BilliardAnalysis(image=image_file)
            analysis.save()
            
            # Return analysis ID
            return JsonResponse({
                'success': True,
                'analysis_id': analysis.id,
                'redirect_url': reverse('process_analysis', args=[analysis.id])
            })
        else:  # Regular form submission
            form = BilliardImageForm(request.POST, request.FILES)
            if form.is_valid():
                analysis = form.save()
                return redirect('process_analysis', analysis_id=analysis.id)
    
    # GET request or invalid form
    form = BilliardImageForm()
    return render(request, 'analysis_app/index.html', {'form': form})

def process_analysis(request, analysis_id):
    """Process image analysis workflow"""
    analysis = get_object_or_404(BilliardAnalysis, id=analysis_id)
    
    try:
        # Get image path
        image_path = analysis.image.path  # Use .path instead of concatenating paths
        print(f"[Debug] Image path: {image_path}")
        
        # Ensure image exists
        if not os.path.exists(image_path):
            analysis.text_result = "Unable to find the uploaded image file."
            analysis.save()
            return render(request, 'analysis_app/analysis.html', {'analysis': analysis})
        
        # Set environment variables
        env = os.environ.copy()
        env["BILLIARD_IMAGE_PATH"] = image_path
        
        # Add the environment variable for the path of the weight file
        weights_dir = os.path.join(PROJECT_ROOT, "NineBallPocketNoNine", "weights")
        os.makedirs(weights_dir, exist_ok=True)
        
        # Try to search for the weight file
        for weight_name in ["last.pt","best.pt" ]:
            weight_path = os.path.join(weights_dir, weight_name)
            if os.path.exists(weight_path):
                env["YOLO_WEIGHT_PATH"] = weight_path
                print(f"[Debug] Using weight file: {weight_path}")
                break
        
        # 1. Call promptFromGPT to generate analysis data
        prompt_script = os.path.join(PROJECT_ROOT, "script", "promptFromGPT.py")
        
        # Get current working directory (Django project directory)
        current_dir = os.getcwd()
        print(f"[Debug] Current working directory: {current_dir}")
        
        prompt_result = run_script(prompt_script, env=env)
        print("[Debug] Calling promptFromGPT.py script...")

        if not prompt_result:
            analysis.text_result = "Unable to analyze the image. Please check if the image is clear and contains billiard balls."
            analysis.save()
            return render(request, 'analysis_app/analysis.html', {'analysis': analysis})
        
        # Check if billiard_analysis.json file was generated (in current working directory)
        json_path = os.path.join(current_dir, "billiard_analysis.json")
        print("[Debug] Prompt generated successfully")
        if not os.path.exists(json_path):
            analysis.text_result = "Failed to generate analysis data. Please ensure the image contains a complete billiards scene."
            analysis.save()
            return render(request, 'analysis_app/analysis.html', {'analysis': analysis})
            
        # Read JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
            
            # Check if there are error information in JSON
            if "error" in analysis_data:
                print(f"[Debug] Analysis contains error information: {analysis_data['error']}")
                analysis.json_result = analysis_data
                analysis.text_result = analysis_data.get("message", "Error occurred during analysis")
                analysis.save()
                # Return result page, don't continue processing detection image and deep analysis
                return render(request, 'analysis_app/analysis.html', {'analysis': analysis})
            
            analysis.json_result = analysis_data
        
        # Only search for and save detection images when detection was successful
        if "error" not in analysis.json_result:
            # Find YOLO detection result images
            yolo_runs_dir = os.path.join(PROJECT_ROOT, "yolov5", "runs", "detect")
            print(f"[Debug] Looking for YOLO detection results directory: {yolo_runs_dir}")
            
            if os.path.exists(yolo_runs_dir):
                # Get all directories starting with "exp", sorted by creation time
                exp_dirs = [d for d in os.listdir(yolo_runs_dir) 
                          if d.startswith("exp") and os.path.isdir(os.path.join(yolo_runs_dir, d))]
                
                if exp_dirs:
                    # Sort by creation time to get the latest directory
                    latest_exp = max(exp_dirs, key=lambda d: os.path.getctime(os.path.join(yolo_runs_dir, d)))
                    exp_path = os.path.join(yolo_runs_dir, latest_exp)
                    print(f"[Debug] Found latest detection results directory: {exp_path}")
                    
                    # Get image files in the directory
                    image_files = [f for f in os.listdir(exp_path) 
                                 if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                    
                    if image_files:
                        # Get the latest image file
                        latest_image = max(image_files, key=lambda f: os.path.getctime(os.path.join(exp_path, f)))
                        detected_image_path = os.path.join(exp_path, latest_image)
                        print(f"[Debug] Found detection result image: {detected_image_path}")
                        
                        # Save detection image to media directory
                        with open(detected_image_path, 'rb') as f:
                            detected_image_content = f.read()
                            # Create temporary file object
                            content_file = ContentFile(detected_image_content)
                            # Use the naming function in models.py directly
                            analysis.detected_image.save(os.path.basename(detected_image_path), content_file, save=False)
                            
                            print(f"[Debug] Saved detection image to: {analysis.detected_image.path}")
        
        # 2. Call Deepseek.py to generate analysis recommendations
        deepseek_script = os.path.join(PROJECT_ROOT, "script", "Deepseek.py")
        print("[Debug] Calling Deepseek.py script...")
        deepseek_result = run_script(deepseek_script)
        
        # Check if analysis_result.txt file was generated (in current working directory)
        result_path = os.path.join(current_dir, "analysis_result.txt")
        if os.path.exists(result_path):
            with open(result_path, 'r', encoding='utf-8') as f:
                analysis.text_result = f.read()
        else:
            analysis.text_result = deepseek_result if deepseek_result else "Unable to get analysis recommendations"
        
        analysis.save()
        
    except Exception as e:
        analysis.text_result = f"Error during processing: {str(e)}"
        analysis.save()
    
    return render(request, 'analysis_app/analysis.html', {'analysis': analysis})

def run_script(script_path, env=None):
    """Run Python script and get output"""
    try:
        # Get script directory
        script_dir = os.path.dirname(script_path)
        print(f"[Debug] Script path: {script_dir}")
        
        if env and "BILLIARD_IMAGE_PATH" in env:
            print(f"[Debug] Image path: {env['BILLIARD_IMAGE_PATH']}")
        
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            encoding='utf-8',
            errors='replace'
        )
        
        stdout, stderr = process.communicate(timeout=180)
        print(f"[Debug] Script output: {stdout}")
        print(f"[Debug] YOLO output: {stderr}")
        
        if process.returncode != 0:
            print(f"Script returned error code: {process.returncode}")
            return None
            
        return stdout
    except Exception as e:
        print(f"Error executing script: {str(e)}")
        return None