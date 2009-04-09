"""
Generic Test case
"""
__docformat__ = 'restructuredtext'

import unittest
import doctest
import sys
import os
import shutil
import popen2
import subprocess
import virtualenv as m_virtualenv
from os import makedirs as mkdir
from shutil import copy
from zc.buildout.buildout import Buildout
from zc.buildout import buildout as bo
from zc.buildout.testing import *


current_dir = os.path.abspath(os.path.dirname(__file__))

def rmdir(*args):
    dirname = os.path.join(*args)
    if os.path.isdir(dirname):
        shutil.rmtree(dirname)

def sh(cmd, in_data=None):
    _cmd = cmd
    print cmd
    p = subprocess.Popen([_cmd], shell=True,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, close_fds=True)

    if in_data is not None:
        p.stdin.write(in_data)

    p.stdin.close()

    print p.stdout.read()

def ls(*args):
    dirname = os.path.join(*args)
    if os.path.isdir(dirname):
        filenames = os.listdir(dirname)
        for filename in sorted(filenames):
            print filename
    else:
        print 'No directory named %s' % dirname

def cd(*args):
    dirname = os.path.join(*args)
    os.chdir(dirname)

def config(filename):
    return os.path.join(current_dir, filename)


def install_eggs_from_pathes(reqs, pathes=None, path='eggs'):
    if pathes:
        env = pkg_resources.Environment()
        ws = pkg_resources.WorkingSet()
        rs=[]
        for req in reqs:
            rs.append(pkg_resources.Requirement.parse(req))

        dists = ws.resolve(rs, env)
        to_copy=[]
        for dist in dists:
            if dist.precedence != pkg_resources.DEVELOP_DIST:
                to_copy.append(dist)

        for dist in to_copy:
            r = dist.as_requirement()
            install('%s'%r, path)


def install_develop_eggs(develop_eggs=None, develop_path='develop-eggs'):
    if develop_eggs:
        for d in develop_eggs:
            install_develop('buildout.minitagificator', develop_path)


def cat(*args, **kwargs):
    filename = os.path.join(*args)
    if os.path.isfile(filename):
        data = open(filename).read()
        if kwargs.get('returndata', False):
           return data
        print data
    else:
        print 'No file named %s' % filename

def touch(*args, **kwargs):
    filename = os.path.join(*args)
    open(filename, 'w').write(kwargs.get('data',''))


def virtualenv(path='.', args=None):
    if not args:
        args = ['--no-site-packages']
    argv = sys.argv[:]
    sys.argv = [sys.executable] + args + [path]
    m_virtualenv.main()
    sys.argv=argv


def virtualenv(path='.', args=None):
    if not args:
        args = ['--no-site-packages']
    argv = sys.argv[:]
    sys.argv = [sys.executable] + args + [path]
    m_virtualenv.main()
    sys.argv=argv


def buildout(*args):
    argv = sys.argv[:]
    sys.argv = ["foo"] + list(args)
    ret = bo.main()
    sys.argv=argv
    return ret

#execdir = os.path.abspath(os.path.dirname(sys.executable))
tempdir = os.getenv('TEMP','/tmp')

def doc_suite(test_dir, setUp=None, tearDown=None, globs=None):
    """Returns a test suite, based on doctests found in /doctest."""
    suite = []
    bp = os.path.dirname(sys.argv[0])
    os.environ['PATH'] = ":".join(
        ["/tmp/buildout.test/bin/",
        bp,
        os.environ.get('PATH', '')]
    )
    if globs is None:
        globs = globals()
        globs["bp"] = bp
        globs["p"] = os.path.dirname(bp)
        #globs["buildout"] = os.path.join(bp, 'buildout')
        globs["python"] = os.path.join(bp, 'py')
    # make a virtualenv with our stuff installed in develop mode inside


    flags = (doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE |
             doctest.REPORT_ONLY_FIRST_FAILURE)

    package_dir = os.path.split(test_dir)[0]
    if package_dir not in sys.path:
        sys.path.append(package_dir)

    doctest_dir = test_dir

    # filtering files on extension
    docs = [os.path.join(doctest_dir, doc) for doc in
            os.listdir(doctest_dir) if doc.endswith('.txt')]

    for ftest in docs:
        test = doctest.DocFileSuite(ftest, optionflags=flags,
                                    globs=globs, setUp=setUp,
                                    tearDown=tearDown,
                                    module_relative=False)
        from zc.buildout.testing import buildoutSetUp
        suite.append(test)

    return unittest.TestSuite(suite)

def test_suite():
    """returns the test suite"""
    return doc_suite(current_dir)

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

