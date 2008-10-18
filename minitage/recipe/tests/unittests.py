#!/usr/bin/env python

# Copyright (C) 2008, Mathieu PASQUET <kiorky@cryptelium.net>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.


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

[part]
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
libraries = a/lib b/lib c/lib
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
        os.makedirs(tmp)

    def tearDown(self):
        """tearDown."""
        shutil.rmtree(tmp)
        recipe = None

    def taestOptions(self):
        """testCommon."""
        bd = Buildout(fp, [])
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        self.assertEquals(recipe.md5, '098f6bcd4621d373cade4e832627b4f6')
        self.assertEquals(recipe.url, 'file://%s' % ft)
        self.assertEquals(recipe.patch_cmd, 'cp')
        self.assertEquals(recipe.patch_options, '-p1')
        self.assertEquals(recipe.make_targets, ['foo'])
        self.assertEquals(recipe.install_targets, ['bar'])
        self.assertEquals(recipe.tmp_directory,
                          os.path.join(
                              d,
                              'dependencies',
                              'a',
                              '__minitage__666__tmp'
                          )
                         )
        self.assertEquals(recipe.prefix,
                          os.path.join(
                              d,
                              'dependencies',
                              'a',
                              'parts', 'part'
                          )
                         )

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
        os.environ['LDFLAGS'] = ''
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        recipe.uname = 'darwin'
        recipe._set_compilation_flags()
        self.assertEquals(os.environ.get('LD_RUN_PATH')
                          , 'a:b:c:d:e:f:%s/lib'% (
                              '/lib:'.join(recipe.minitage_dependencies+\
                                      recipe.minitage_eggs
                                           + [recipe.prefix])
                          )
                         )
        self.assertEquals(os.environ.get('CFLAGS'),
                          '-Ia -Ib -Ic -Id -Ie -If %s' % (
                              '-I%s/include' % (
                                  '/include -I'.join(
                                      recipe.minitage_dependencies+\
                                      recipe.minitage_eggs
                                  )
                              )
                          )
                         )
        self.assertTrue(os.path.join(
            d,
            'dependencies',
            'ldep2',
            'parts',
            'part') in recipe.minitage_dependencies)
        self.assertEquals(os.environ.get('LDFLAGS'),
                          '%s%s' %(
                              ''.join(['-L%s/lib -Wl,-rpath -Wl,%s/lib ' % (s,s) \
                                       for s in ['a','b','c','d','e','f'] \
                                       + recipe.minitage_dependencies +
                                       recipe.minitage_eggs + [recipe.prefix]]),
                              ' -mmacosx-version-min=10.5.0 ',
                          )
                         )

    def testUnpack(self):
        """testUnpack."""
        p = tmp
        os.system("""
                  cd %s
                  touch toto
                  tar cjvf toto.tbz2 toto
                  rm -f toto
                  """ % tmp)
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        recipe._unpack(os.path.join(tmp, 'toto.tbz2'))
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    recipe.tmp_directory, 'toto'
                )
            )
        )

    def testPatch(self):
        """testPatch."""
        p = tmp
        os.system("""
                  cd %s
                  mkdir titi
                  touch titi/toto
                  tar cjvf toto.tbz2 titi
                  mkdir tata
                  echo 'titi'>tata/toto
                  diff -ur titi tata>patch.diff
                  rm -rf titi tata
                  """ % tmp)
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        recipe.tmp_directory = tmp
        recipe._unpack(os.path.join(
            recipe.tmp_directory,
            'toto.tbz2')
        )
        recipe.patch_cmd = 'patch'
        recipe.patch_options = ''
        recipe.patches = [os.path.join(tmp, 'patch.diff')]
        recipe._patch(recipe.tmp_directory)
        self.assertEquals(
            open(
                os.path.join(
                    tmp, 'toto'
                )
            ).read(),
            'titi\n'
        )

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

    def testConfigure(self):
        """testConfigure."""
        p = tmp
        os.system("""
cd %s
echo 'touch foo'>configure
chmod +x configure
""" % (tmp))
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        configure = recipe._choose_configure(tmp)
        recipe._configure(configure)
        self.assertTrue(
            os.path.isfile(
                os.path.join(tmp, 'foo')
            )
        )

    def testMake(self):
        """testMake."""
        p = tmp
        open(
            os.path.join(tmp,'Makefile'),
            'w').write(MAKEFILE)
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        recipe._make(tmp, ['all'])
        self.assertTrue(
            os.path.isfile(
                os.path.join(tmp, 'foo')
            )
        )
        self.assertFalse(
            os.path.isfile(
                os.path.join(tmp, 'install')
            )
        )

    def testMakeInstall(self):
        """testMake."""
        p = tmp
        open(
            os.path.join(tmp,'Makefile'),
            'w').write(MAKEFILE)
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = MinitageCommonRecipe(bd, '666', bd['part'])
        os.system('cd %s;mkdir a;touch a/test' % p)
        recipe.prefix = 'a'
        self.assertTrue(
            os.path.isfile(
                os.path.join(p, 'a', 'test')
            )
        )
        recipe.install_targets = ['install']
        recipe._make_install(tmp)
        self.assertTrue(
            os.path.isfile(
                os.path.join(tmp, 'install')
            )
        )
        self.assertFalse(
            os.path.isfile(
                os.path.join(p, 'a', 'test')
            )
        )
        os.system('cd %s;rm -rf a;mkdir a;touch a/test' % p)
        recipe.prefix = 'a'
        self.assertTrue(
            os.path.isfile(
                os.path.join(p, 'a', 'test')
            )
        )
        recipe.install_targets = ['install-failed']
        self.assertRaises(core.MinimergeError,
                          recipe._make_install,
                          tmp)
        self.assertTrue(
            os.path.isfile(
                os.path.join(p, 'a', 'test')
            )
        )

    def testBuildEgg(self):
        """testBuildEgg."""
        p = tmp
        make_fakeegg(tmp)
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = DURecipe(bd, '666', bd['part'])
        recipe._build_python_package(p)
        self.assertTrue(os.path.isdir(
            os.path.join(p,'build'))
        )

    def testInstallEgg(self):
        """installEgg."""
        p = tmp
        make_fakeegg(tmp)
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = DURecipe(bd, '666', bd['part'])
        recipe._build_python_package(p)
        recipe._install_python_package(p)
        self.assertTrue(os.path.isdir(
            os.path.join(p,'dist'))
        )
        contents = os.listdir(recipe.site_packages_path)
        l = len([f for f in contents if f.startswith('foo')])
        self.assertEquals(l, 1)
        self.assertTrue(
            os.path.isfile(
                os.path.join(d, 'dependencies', 'a', 'bin', 's')
            )
        )

    def testCmmi(self):
        """testCmmi."""
        p = tmp
        os.system("""
cd %s
echo 'touch toto'>configure
chmod +x configure
""" % (tmp))
        open(
            os.path.join(tmp,'Makefile'),
            'w').write(MAKEFILE)
        os.system('cd %s;tar cjvf a.tbz2 a' % d)
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = CMMIRecipe(bd, '666', bd['part'])
        recipe.url = 'file://%s/a.tbz2' % d
        recipe.md5 = None
        recipe.patches = []
        recipe.install()
        for file in 'toto', 'foo', 'bar':
            self.assertTrue(
                os.path.join(tmp,file)
            )

    def testRecipeDu(self):
        """testRecipeDu."""
        p = tmp
        make_fakeegg(tmp)
        os.system('cd %s;tar cjvf b.tbz2 a' % d)
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = DURecipe(bd, '666', bd['part'])
        recipe.url = 'file://%s/b.tbz2' % d
        recipe.md5 = None
        recipe.patches = []
        recipe.install()
        self.assertTrue(os.path.join(tmp, 'bin', 's'))

    def testZCleanup(self):
        p = tmp
        make_fakeegg(tmp)
        os.system('cd %s;tar cjvf b.tbz2 a' % d)
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = DURecipe(bd, '666', bd['part'])
        recipe.url = 'invalid'
        recipe.md5 = None
        recipe.patches = []
        # first will leave the files
        # second will clean them
        try:
            recipe.install()
        except:
            pass
        recipe2 = DURecipe(bd, '666', bd['part'])
        recipe2.url = 'file://%s/b.tbz2' % d
        recipe2.md5 = None
        recipe2.patches = []
        recipe2.install()
        self.assertTrue(os.path.join(tmp, 'bin', 's'))

    def testInstallElementtree(self):
        """testInstallElementtree."""
        p = tmp
        a = os.path.join(p, 'aaaaaaaaaa')
        cache  = os.path.join(p, 'c')
        dcache = os.path.join(p, 'd')
        make_fakeegg(tmp)
        for dir in a, cache, dcache:
            os.makedirs(dir)
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = EGGSRecipe(bd, '666', bd['part'])
        recipe.buildout['buildout']['eggs-directory'] = cache
        recipe.buildout['buildout']['develop-eggs-directory'] = dcache
        recipe.tmp_directory = a
        recipe.patches=[]
        recipe.offline = False
        recipe.md5= None
        recipe.eggs = ['elementtree',]
        ws = recipe.get_workingset()
        self.assertTrue(ws.find(pkg_resources.Requirement.parse('elementtree')))
        recipe.eggs = ['elementtree', 'plone.app.form']
        ws = recipe.get_workingset()
        self.assertTrue(ws.find(pkg_resources.Requirement.parse('elementtree')))
        self.assertTrue(ws.find(pkg_resources.Requirement.parse('plone.app.form')))

    def testGetCommonDist(self):
        """testGetCommonDist."""
        p = tmp
        a = os.path.join(p, 'aaaaaaaaaa')
        cache  = os.path.join(p, 'c')
        dcache = os.path.join(p, 'd')
        make_fakeegg(tmp)
        for dir in a, cache, dcache:
            os.makedirs(dir)
        bd = Buildout(fp, [])
        bd.offline = False
        recipe = EGGSRecipe(bd, '666', bd['part'])
        recipe.eggs = ['elementtree',]
        recipe.buildout['buildout']['eggs-directory'] = cache
        recipe.buildout['buildout']['develop-eggs-directory'] = dcache
        recipe.tmp_directory = a
        recipe.patches=[]
        recipe.offline = False
        recipe.md5= None
        e = pkg_resources.Environment([cache], python=recipe.executable_version)
        e.scan()
        d = e['minitage.recipe'][0]
        r = pkg_resources.Requirement.parse('minitage.recipe')
        ws = pkg_resources.WorkingSet()
        dist = recipe._get_dist(d, cache, ws)
        self.assertEquals(dist.project_name, 'minitage.recipe')

    def testGetDist(self):
        """testGetDist."""
        p = tmp
        a = os.path.join(p, 'aaaaaaaaaa')
        cache  = os.path.join(p, 'c')
        dcache = os.path.join(p, 'd')
        make_fakeegg(a)
        for dir in cache, dcache:
            os.makedirs(dir)
        os.system("""cd %s
                  cd aaaaaaaaaa
                  %s setup.py sdist
                  cp dist/foo-1.0.tar.gz ..
                  cp dist/foo-1.0.tar.gz /home/kiorky/tmp/foo-1.0.tar.gz
                  """ % (
                      p, sys.executable)
                 )

        bd = Buildout(fp, [])
        bd.offline = False
        recipe = EGGSRecipe(bd, '666', bd['part'])
        recipe.eggs = ['elementtree',]
        recipe.buildout['buildout']['eggs-directory'] = cache
        recipe.buildout['buildout']['develop-eggs-directory'] = dcache
        recipe.tmp_directory = a
        recipe.patches=[]
        recipe.offline = False
        recipe.md5= None
        req = pkg_resources.Requirement.parse('foo')
        pi = setuptools.package_index.PackageIndex()
        pi.add_find_links([tmp])
        d = pi.obtain(req)
        ws = pkg_resources.WorkingSet()
        dist = recipe._get_dist(d, cache, ws)
        self.assertTrue(cache in dist.location)
        self.assertEquals(dist.project_name, 'foo')

    def testPatchDist(self):
        """testPatchDist."""
        p = tmp
        a = os.path.join(p, 'aaaaaaaaaa')
        cache  = os.path.join(p, 'c')
        dcache = os.path.join(p, 'd')
        make_fakeegg(a)
        for dir in cache, dcache:
            os.makedirs(dir)
        os.system("""cd %s
                  cd aaaaaaaaaa
                  %s setup.py sdist
                  cp dist/foo-1.0.tar.gz ..
                  cp dist/foo-1.0.tar.gz /home/kiorky/tmp/foo-1.0.tar.gz
                  """ % (
                      p, sys.executable)
                 )

        bd = Buildout(fp, [])
        bd.offline = False
        recipe = EGGSRecipe(bd, '666', bd['part'])
        recipe.eggs = ['elementtree',]
        recipe.buildout['buildout']['eggs-directory'] = cache
        recipe.buildout['buildout']['develop-eggs-directory'] = dcache
        recipe.tmp_directory = a
        recipe.patches=[]
        recipe.offline = False
        recipe.md5= None
        req = pkg_resources.Requirement.parse('foo')
        pi = setuptools.package_index.PackageIndex()
        pi.add_find_links([tmp])
        d = pi.obtain(req)
        ws = pkg_resources.WorkingSet()


        p1 = os.path.join(p, 'a.diff')
        p2 = os.path.join(p, 'b.diff')
        open(p1, 'w').write("""
diff -ur old/setup.py new/setup.py
--- old/setup.py        2008-05-30 17:53:06.305385925 +0000
+++ new/setup.py        2008-05-30 17:53:48.309233006 +0000
@@ -10,3 +10,4 @@
             packages=find_packages()
 )

+# i am a comment which changed
""")
        open(p2, 'w').write("""
--- old/bar.c   2008-05-30 17:36:43.215346219 +0000
+++ new/bar.c   2008-05-30 17:37:36.220200916 +0000
@@ -20,3 +20,4 @@
 }


+/* changed */
""")
        recipe.uname = 'linux'
        recipe.options['foo-patches'] =  p1
        recipe.options['foo-linux-patches'] = p2
        recipe.options['foo-patch-options'] =  '-p1'
        recipe.options['foo-patch-binary'] = 'patch'

        location = d.location
        if not os.path.isdir(location):
            location = tempfile.mkdtemp()
            recipe._unpack(d.location, location)
            location = recipe._get_compil_dir(location)
        recipe.options['compile-directory'] = location
        recipe._patch(location, d)
        l1 =  open(os.path.join(
            location, 'setup.py'), 'r').readlines()
        l2 =  open(os.path.join(
            location, 'bar.c'), 'r').readlines()
        self.assertEquals( '# i am a comment which changed\n', l1[-1])
        self.assertEquals( '/* changed */\n', l2[-1])

def test_suite():
    return unittest.makeSuite(RecipeTest)

if __name__ == '__main__' :
    unittest.TextTestRunner(verbosity=2).run(test_suite())


# vim:set et sts=4 ts=4 tw=80:
