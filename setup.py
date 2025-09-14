from setuptools import setup, find_packages

with open('README.md', 'r') as file:
    long_description = file.read()

setup(
    name='connor_nlp',
    version='1.0.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    include_package_data=True,
    package_data={
        'connor': ['resources/stopwords.json'],
    },
    install_requires=[
        "numpy==2.3.3"
        "odfpy==1.4.1"
        "openpyxl==3.1.5"
        "PyPDF2==3.0.1"
        "python_docx==1.2.0"
        "python_pptx==1.0.2"
        "scikit_learn==1.7.2"
        "sentence_transformers==3.3.1"
    ],
    entry_points={
        'console_scripts': [
            'connor=main:main',
        ],
    },
    author='Ycatsh',
    description='Fast file organizer and classifier that categorizes file based on content using NLP',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/ycatsh/connor',
    license='MIT',
    license_file='LICENSE',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.10'
)
