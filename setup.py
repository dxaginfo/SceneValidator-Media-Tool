from setuptools import setup, find_packages

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setup(
    name='scene_validator',
    version='0.1.0',
    author='Media Automation Tools Team',
    author_email='dev@example.com',
    description='Media scene validation tool using Gemini API and Google Cloud',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/dxaginfo/SceneValidator-Media-Tool',
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.10',
    install_requires=[
        'python-dotenv',
        'requests',
        'flask',
        'gunicorn',
        'firebase-admin',
        'google-cloud-storage',
        'google-cloud-firestore',
        'google-generativeai',
        'ffmpeg-python',
        'opencv-python',
        'numpy',
        'pillow',
    ],
)
