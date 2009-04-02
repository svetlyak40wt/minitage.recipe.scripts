*********************************************
Recipe for compiling and installing software
*********************************************

.. contents::

=======================
README
=======================


The recipe has those entry point:
    - cmmi: install configure/make/make install softwares
    - fetch: fetch something somewhere
    - eggs: install python eggs / packages 'setuptoolisables'
    - printer: print or dump to a file all versions needed to achieve eggs
      requirements (versions.cfg made easy)
    - scripts: install scripts from an egg and install egg dependencies if they
      are not already in the cache

The reasons why i have rewrite yet another buildout recipe builder are:
    - Support for downloading stuff
    - Support on the fly patchs
    - Support hookss
    - Support for distutils
    - Robust offline mode
    - We like pypi, but offer a mode to not use it if we do not want to.

