import os, sys
from setuptools import setup, find_packages
setupdir = os.path.abspath(
    os.path.dirname(__file__)
)
os.chdir(setupdir)

name='minitage.recipe'
version = '1.8'

def read(*rnames):
    return open(
        os.path.join(setupdir, *rnames)
    ).read()

long_description = (
    read('README.txt')
    + '\n'\
    + read('src', 'minitage', 'recipe', 'tests', 'shared.txt')
    + '\n'
    + read('src', 'minitage', 'recipe', 'tests', 'scripts.txt')
    + '\n'
    + read('src', 'minitage', 'recipe', 'tests', 'egg.txt')
    + '\n'
    + read('src', 'minitage', 'recipe', 'tests', 'cmmi.txt')
    + '\n'
    + read('src', 'minitage', 'recipe', 'tests', 'fetch.txt')
    + '\n'
    + read('src', 'minitage', 'recipe', 'tests', 'printer.txt')
    + '\n'
    + read('src', 'minitage', 'recipe', 'tests', 'wsgi.txt')
    + '\n'
    + read('src', 'minitage', 'recipe', 'tests', 'api.txt')
    + '\n'
    + read('CHANGES.txt')
    + '\n'
)

if 'RST_TEST' in os.environ:
    print long_description
    sys.exit(0)

setup(
    name=name,
    version=version,
    description="zc.buildout recipes to compile and install software or python packages and generate scripts or configuration files.",
    long_description= long_description,
    classifiers=[
        'Framework :: Buildout',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    keywords='development buildout recipe',
    author='Mathieu Pasquet',
    author_email='kiorky@cryptelium.net',
    url='http://cheeseshop.python.org/pypi/%s' % name,
    license='GPL',
    packages=find_packages('src'),
    package_dir = {'': 'src'},
    namespace_packages=['minitage', name],
    include_package_data=True,
    zip_safe=False,
    install_requires = [
        'zc.buildout',
        'setuptools',
        'minitage.core',
        'iniparse',
    ],
    extras_require={'test': ['IPython', 'zope.testing', 'mocker']},
    #tests_require = ['zope.testing'],
    #test_suite = '%s.tests.test_suite' % name,
    # adding zdu, setuptools seems to order recipes executions
    # in akphabetical order for entry points
    # workaround when using the 2 recipes in the same buildout.
    entry_points = {
        'zc.buildout' : [
            'default = %s:Recipe' % name,
            'du = %s:Recipe' % 'minitage.recipe.du',
            'fetch = %s:Recipe' % 'minitage.recipe.fetch',
            'egg = %s:Recipe' % 'minitage.recipe.egg',
            'printer = %s:Recipe' % 'minitage.recipe.printer',
            'zdu = %s:Recipe' % 'minitage.recipe.du',
            'cmmi = %s:Recipe' % 'minitage.recipe.cmmi',
            'scripts = %s:Recipe' % 'minitage.recipe.scripts',
            'script = %s:Recipe' % 'minitage.recipe.scripts',
            'eggs = %s:Recipe' % 'minitage.recipe.scripts',
            'wsgi = %s:Recipe' % 'minitage.recipe.wsgi',
        ]
    },
)

