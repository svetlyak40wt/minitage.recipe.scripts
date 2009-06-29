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


import os
import shutil
try:
    from hashlib import sha1
except ImportError: # Python < 2.5
    from sha import new as sha1

from minitage.recipe import common
from minitage.core import core

class Recipe(common.MinitageCommonRecipe):
    """zc.buildout recipe for compiling and installing software"""

    def __init__(self, buildout, name, options):

        common.MinitageCommonRecipe.__init__(self,
                                             buildout, name, options)
        # handle share mode, compatibility with zc.recipe.cmmi
        self.shared = False
        self.shared_top = os.path.join(self.download_cache, 'cmmi')
        if not os.path.isdir(self.shared_top):
                os.makedirs(self.shared_top)
        if 'shared' in self.options:
            self.shared = os.path.join(self.shared_top,
                         self._state_hash())
            self.prefix = options['location'] = self.shared

    def install(self):
        """Install the recipe."""
        # initialise working directories
        for path in [self.prefix, self.tmp_directory]:
            if not os.path.exists(path):
                os.makedirs(path)
        try:
            cwd = os.getcwd()
            # downloading or get the path
            # in the cache if we are offline
            fname = self._download(md5=self.md5)

            # preconfigure hook
            self._call_hook('pre-unpack-hook')

            # unpack
            self._unpack(fname)

            # get default compilation directory
            self.compil_dir = self._get_compil_dir(self.tmp_directory)

            # set path
            self._set_path()

            # set pkgconfigpath
            self._set_pkgconfigpath()

            # set compile path
            self._set_compilation_flags()

            # set pypath
            self._set_py_path()

            # preconfigure hook
            self._call_hook('post-unpack-hook')

            # choose configure
            self.configure = self._choose_configure(self.compil_dir)
            self.options['compile-directory'] = self.build_dir

            # apply patches
            self._patch(self.build_dir)

            # preconfigure hook
            self._call_hook('pre-configure-hook')

            # autogen, maybe
            self._autogen()

            # run configure
            self._configure(self.configure)

            # postconfigure/premake hook
            self._call_hook('pre-make-hook')

            # running make
            self._make(self.build_dir, self.make_targets)

            # post build hook
            self._call_hook('post-build-hook')

            # installing
            self._make_install(self.build_dir)

            # post hook
            self._call_hook('post-make-hook')

            # cleaning
            for path in self.build_dir, self.tmp_directory:
                if os.path.isdir(path):
                    shutil.rmtree(path)

            # regaining original cwd in case we changed build directory
            # during build process.
            os.chdir(cwd)
            self.logger.info('Completed install.')
        except Exception, e:
            raise
            self.logger.error('Compilation error. '
                              'The package is left as is at %s where '
                      'you can inspect what went wrong' % self.tmp_directory)
            self.logger.error('Message was:\n\t%s' % e)
            raise core.MinimergeError('Recipe failed, cant install.')

        return []

