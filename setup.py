from setuptools import setup, Extension, find_packages
import os

# Read requirements from requirements.txt
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

# Read version directly
version = "0.1.1"

# Read long description from README.md
with open('README.md', encoding='utf-8') as f:
    long_description = f.read()

core_module = Extension('core',
                       sources=['core/shell.c', 'core/shell_python.c'],
                       include_dirs=['core'])

setup(
    name='shell-llm',
    version=version,
    description='Interactive shell with LLM-powered features',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='LLM Shell Team',
    author_email='your.email@example.com',  # Update this
    url='https://github.com/jrdfm/shell-llm',  # Update this
    py_modules=['llm', 'formatters', 'shell', 'error_handler', 'ui', 'models', 
                'completions', 'utils', '__main__', '__init__'],
    ext_modules=[core_module],
    install_requires=requirements,
    python_requires='>=3.8',
    entry_points={
        'console_scripts': [
            'shell-llm=shell:main',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',  # Update based on your license
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    keywords='shell, llm, assistant, terminal',
    project_urls={
        'Bug Reports': 'https://github.com/jrdfm/shell-llm/issues',  # Update
        'Source': 'https://github.com/jrdfm/shell-llm',  # Update
    },
    include_package_data=True,
) 