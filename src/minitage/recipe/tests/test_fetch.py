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

    def testFetch(self):
        """testFetch."""



def test_suite():
    return unittest.makeSuite(RecipeTest)

if __name__ == '__main__' :
    unittest.TextTestRunner(verbosity=2).run(test_suite())


# vim:set et sts=4 ts=4 tw=80:
