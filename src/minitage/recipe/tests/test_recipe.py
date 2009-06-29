# Copyright (C) 2009, Mathieu PASQUET <kiorky@cryptelium.net>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the <ORGANIZATION> nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.




__docformat__ = 'restructuredtext en'

import tempfile
import unittest
import os
import sys
import shutil


import zc.buildout
from zc.buildout.buildout import Buildout
import pkg_resources
import setuptools

from minitage.core.makers.interfaces import IMakerFactory
from minitage.recipe.common import MinitageCommonRecipe
from minitage.recipe.egg  import Recipe as EGGSRecipe
from minitage.recipe.du   import Recipe as DURecipe
from minitage.recipe.cmmi import Recipe as CMMIRecipe
from minitage.core.common import md5sum
from minitage.core import core
from minitage.core.tests.test_common import write

d = tempfile.mkdtemp()
# make 2 depth "../.."
e = os.path.join(d, 'dependencies' ,'a')
os.makedirs(e)
tmp = os.path.join(d, 'a')
fp = os.path.join(e ,'buildout.cfg')
ft = os.path.join(e ,'buildouttest')
CMMI = """
[buildout]
parts=part
offline=true

[egg]
eggs = elementtree

[env]
foo = bartest

[part]
environment = env
eggs = elementtree
minitage-eggs = legg1
minitage-dependencies = ldep2
pkgconfigpath = 1a 2b
                3c
path = 1 2
       3
pythonpath = a b
             c
name=part
includes = a b c
           d e f
libraries = c
library-dirs = a/lib b/lib c/lib
            d/lib e/lib f/lib
rpath = a b c
        d e f
recipe = minitage.recipe:cmmi
url=file://%s
hook = false
md5sum=098f6bcd4621d373cade4e832627b4f6
make-binary=make
patch-binary=cp
patch-options=-p1
gmake=true
make-targets=foo
make-install-targets=bar
patches = %s/patch.diff

[minitage]
dependencies = lib1 lib2
               lib3
eggs = egg1 egg2
       egg3
""" % (ft, d)

MAKEFILE = """
all: bar foo

bar:
\ttouch bar

foo:
\ttouch foo

install-failed:
\tmkdir toto
\tchmod 666 toto
\ttouch toto/toto

install:
\ttouch install

"""


def make_fakeegg(tmp):
    setup = """
import os
from setuptools import setup, Extension, find_packages
setup(name='foo',
            version='1.0',
            scripts=['s'],
            author='foo',
            zip_safe = False,
            ext_modules=[Extension('bar', ['bar.c'])],
            packages=find_packages()
)

"""
    c = """
#include <Python.h>
static PyObject *
mytest(PyObject *self, PyObject *args)
{
        printf("hello");
        Py_INCREF(Py_None);
        return Py_None;
}

static PyMethodDef mytestm[] = {
        {"mytest",  mytest, METH_VARARGS},
        {NULL, NULL, 0, NULL}  /* Sentinel */
};

PyMODINIT_FUNC
bar(void)
{
    (void) Py_InitModule("bar", mytestm);
}


"""
    os.makedirs(os.path.join(tmp,'foo'))
    open(os.path.join(tmp, 'setup.py'), 'w').write(setup)
    open(os.path.join(tmp, 's'), 'w').write('foo')
    open(
        os.path.join(tmp, 'foo', '__init__.py'), 'w'
    ).write('print 1')
    open(
        os.path.join(tmp, 'bar.c'), 'w'
    ).write(c)


def write(f, data):
    open(ft, 'w').write('test')
    f = open(fp, 'w')
    f.write(data)
    f.flush()
    f.close()

class RecipeTest(unittest.TestCase):
    """Test usage for minimerge."""

    def setUp(self):
        """setUp."""
        os.chdir('/')
        write(fp, CMMI)
        if not os.path.exists(tmp):
            os.makedirs(tmp)
        os.environ['ld_run_path']     =  os.environ.get('LD_RUN_PATH', '')
        os.environ['cflags']          =  os.environ.get('CFLAGS', '')
        os.environ['pkg_config_path'] =  os.environ.get('PKG_CONFIG_PATH', '')
        os.environ['ldflags']         =  os.environ.get('LDFLAGS', '')

    def tearDown(self):
        """tearDown."""
        os.environ['LD_RUN_PATH']     =  os.environ['ld_run_path']
        os.environ['CFLAGS']          =  os.environ['cflags']
        os.environ['PKG_CONFIG_PATH'] =  os.environ['pkg_config_path']
        os.environ['LDFLAGS']         =  os.environ['ldflags']
        shutil.rmtree(tmp)
        recipe = None

    def tastEnc(self):
        """testCommon."""
        bd = Buildout(fp, [])
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        self.assertEquals(os.environ['foo', 'bartest'])

    def testdownload(self):
        """testDownload."""
        p = tmp
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        ret = recipe._download()
        self.assertTrue(
            os.path.isfile(
                os.path.join(recipe.download_cache, 'buildouttest')
            )
        )
        p = tmp
        bd = Buildout(fp, [])
        bd.offline = True
        open(os.path.join(p, 'a'), 'w').write('test')
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        recipe.url = 'http://foo/a'
        recipe.download_cache = p
        ret = recipe._download()
        self.assertEquals(
            ret,
            os.path.join(p, 'a')
        )

    def testPyPath(self):
        """testPyPath."""
        p = tmp
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        ppath = sys.path
        recipe._set_py_path()
        nppath = os.environ['PYTHONPATH']
        for elem in [recipe.buildout['buildout']['directory'],
                     recipe.options['location'],]\
                    + ['/eggs/egg1/parts/%s' % (
                            recipe.site_packages
                        ),
                        '/eggs/egg2/parts/%s' % (
                           recipe.site_packages
                        ),
                        '/eggs/legg1/parts/%s' % (
                            recipe.site_packages
                        ),
                        '/eggs/egg3/parts/%s'  % (
                           recipe.site_packages
                        ),
                    ]:
            print elem
            self.assertTrue(elem in nppath)

    def testPath(self):
        """testPath."""
        p = tmp
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        recipe._set_path()
        path = os.environ['PATH']
        for elem in [recipe.buildout['buildout']['directory'],
                     recipe.options['location'],]\
                    + os.environ.get('PATH','').split(':') :
            self.assertTrue(elem in path)

    def testPkgconfigpath(self):
        """testPkgconfigpath."""
        p = tmp
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        recipe._set_pkgconfigpath()
        path = os.environ.get(
            'PKG_CONFIG_PATH', ''
        )
        for elem in ['1a']\
                    + os.environ.get('PKG_CONFIG_PATH','').split(':')\
                    + ['%s/lib/pkgconfig' % dep \
                       for dep in recipe.minitage_dependencies]:
            self.assertTrue(elem in path)

    def testCompilationFlags(self):
        """testCompilationFlags."""
        p = tmp
        bd = Buildout(fp, [])
        bd.offline = False
        os.environ['LD_RUN_PATH'] = ''
        os.environ['CFLAGS'] = ''
        os.environ['PKG_CONFIG_PATH'] = ''
        os.environ['LDFLAGS'] = ''
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        recipe.uname = 'darwin'
        recipe._set_compilation_flags()

        a = os.environ.get('LD_RUN_PATH')
        b = 'a:b:c:d:e:f:%s/lib'% (
            '/lib:'.join(recipe.minitage_dependencies
                         + [recipe.prefix])
                          )
        self.assertEquals(a, b)

        a = os.environ.get('CFLAGS')
        b = '-Ia -Ib -Ic -Id -Ie -If %s' % (
            '-I%s/include' % (
                '/include -I'.join(
                    recipe.minitage_dependencies
                )
            )
        )
        self.assertEquals(a, b)

        self.assertTrue(os.path.join(d, 'dependencies', 'ldep2', 'parts', 'part') in recipe.minitage_dependencies)

        a = '%s%s' %(
                ''.join(['-L%s/lib -Wl,-rpath -Wl,%s/lib ' % (s,s) \
                         for s in ['a','b','c','d','e','f'] \
                         + recipe.minitage_dependencies + [recipe.prefix]]),
                ' -mmacosx-version-min=10.5.0   -lc',
            )
        b = os.environ.get('LDFLAGS')
        self.assertEquals(a, b)

    def testCallHook(self):
        """testCallHook."""
        p = tmp
        hook = os.path.join(tmp, 'toto.py')
        os.system("""
cd %s
cat << EOF  > %s
import os
def write(options, buildout):
    open(
        os.path.join('%s','foo'),
        'w').write('foo')
EOF""" % (tmp, hook, tmp))
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        recipe.options['hook'] = '%s:write' % hook
        recipe._call_hook('hook')
        self.assertEquals(
            open(
                os.path.join(tmp, 'foo')
            ).read(),
            'foo'
        )

    def testGetCompilDir(self):
        """testGetCompilDir."""
        p = tmp
        os.system("""
cd %s
mkdir .download
mkdir tutu
mkdir tutu/.download
""" % (tmp))
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        directory = recipe._get_compil_dir(tmp)
        self.assertEquals(directory, os.path.join(tmp, 'tutu'))

    def testChooseConfigure(self):
        """testChooseConfigure."""
        p = tmp
        os.system("""
cd %s
touch configure
mkdir toto
touch toto/test
""" % (tmp))
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        configure = recipe._choose_configure(tmp)
        self.assertEquals(configure, os.path.join(tmp, 'configure'))
        self.assertEquals(recipe.build_dir, tmp)

        recipe.build_dir = os.path.join(tmp, 'toto')
        recipe.configure = 'test'
        configure = recipe._choose_configure(recipe.build_dir)
        self.assertEquals(configure, os.path.join(tmp, 'toto', 'test'))
        self.assertEquals(recipe.build_dir, os.path.join(tmp, 'toto'))

def test_suite():
    return unittest.makeSuite(RecipeTest)

if __name__ == '__main__' :
    unittest.TextTestRunner(verbosity=2).run(test_suite())


# vim:set et sts=4 ts=4 tw=80:
