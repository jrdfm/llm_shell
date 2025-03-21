from setuptools import setup, Extension

core_module = Extension('core',
                       sources=['core/shell.c', 'core/shell_python.c'],
                       include_dirs=['core'])

setup(name='llm_shell',
      version='0.1',
      description='Interactive shell with C core',
      ext_modules=[core_module],
      python_requires='>=3.8') 