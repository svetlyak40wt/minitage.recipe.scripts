import os
from setuptools import setup, find_packages
setupdir = os.path.abspath(
    os.path.dirname(__file__)
)
os.chdir(setupdir)

name='minitage.recipe'
version = '0.15'

def read(rnames):
    return open(
        os.path.join(setupdir, rnames)
    ).read()

setup(
    name=name,
    version=version,
    description="zc.buildout recipe for compiling and installing software or python packages.",
    long_description= (
        read('README.txt')
        + '\n' +
        read('CHANGES.txt')
        + '\n'
    ),
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
        'minitage.core'
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
            'zdu = %s:Recipe' % 'minitage.recipe.du',
            'cmmi = %s:Recipe' % 'minitage.recipe.cmmi',
            'scripts = %s:Recipe' % 'minitage.recipe.scripts',
        ]
    },
)

