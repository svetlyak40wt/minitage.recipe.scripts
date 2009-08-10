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

import os
import shutil
import tempfile
from minitage.recipe import common
from minitage.core.common import get_from_cache, system, splitstrip, test_md5
from minitage.core.unpackers import *
from distutils.dir_util import copy_tree

def dump_write(content, dump_path):
    f = open(dump_path, 'w')
    f.write(content)
    f.close()


class Recipe(common.MinitageCommonRecipe):
    """
    Downloads something from somewhere.
    """

    def update(self):
        """update."""

        self.install()

    def install(self):
        """installs an egg
        """
        self.cache = os.path.join(
            self.buildout['buildout']['directory'],
            'cache'
        )
        directories = []
        self.logger.info('Start checkouts')
        for url, url_infos in self.urls.items():
            dest = url_infos.get('directory')
            if not dest:
                dest = os.path.basename(dest)
            if not dest.startswith('/'):
                dest = os.path.join(
                    self.options['location'],
                    dest
                )
            cache_fname = os.path.basename(url)
            cache_downloaded = os.path.join(self.cache, cache_fname)
            downloaded = False
            fname = ''
            if os.path.exists(cache_downloaded):
                if test_md5(cache_downloaded, url_infos.get('revision', 1)):
                    downloaded = True
                    self.logger.info('%s is already downloaded' %
                                     cache_downloaded)
                    fname = cache_downloaded
            if not downloaded:
                fname = self._download(url=url,
                                       destination=dest,
                                       cache=False)

            if ('unpack' in self.options):
                try:
                    # try to unpack
                    f = IUnpackerFactory()
                    u = f(fname)
                    tmpdest = tempfile.mkdtemp()
                    ftmpdest = tmpdest
                    if u:
                        if os.path.exists(dest):
                            c = len(os.listdir(dest))
                            if c > 1:
                                shutil.rmtree(dest)
                                os.makedirs(dest)
                        u.unpack(fname, tmpdest)
                        if not os.path.exists(self.cache):
                            os.makedirs(self.cache)
                        os.rename(fname, cache_downloaded)
                        c = os.listdir(tmpdest)
                        if len(c) == 1:
                            ftmpdest = os.path.join(tmpdest, c[0])
                        copy_tree(ftmpdest, dest)
                        shutil.rmtree(tmpdest)
                except Exception, e:
                    message = 'Can\'t install file %s in its destination %s.'
            self.logger.info('Completed dowbload of %s in %s' % (url, dest))
            directories.append(fname)
        self.logger.info('Finnished checkouts')
        return []

# vim:set et sts=4 ts=4 tw=80:
