from setuptools import setup, find_packages

setup(
    name="yolov5",
    version="7.0",  # 与你的版本一致
    packages=find_packages(include=['yolov5*']),  # 只包含yolov5相关包
    package_dir={'': '.'},  # 指定根目录
    install_requires=[
        'matplotlib>=3.2.2',
        'numpy>=1.18.5',
        'opencv-python>=4.1.1',
        'Pillow>=7.1.2',
        'PyYAML>=5.3.1',
        'requests>=2.23.0',
        'scipy>=1.4.1',
        'torch>=1.7.0',
        'torchvision>=0.8.1',
        'tqdm>=4.41.0',
        'pandas>=1.1.4',
        'seaborn>=0.11.0',
    ],
    python_requires='>=3.8',
)