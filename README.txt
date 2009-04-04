*********************************************
Recipe for compiling and installing software
*********************************************

.. contents::

=======================
README
=======================

The recipe has those entry point:
    - *cmmi*: install configure/make/make install softwares
    - *fetch*: fetch something somewhere
    - *eggs*: install python eggs / packages 'setuptoolisables'
    - *printer*: print or dump to a file all versions needed to achieve eggs
      requirements (versions.cfg made easy)
    - *scripts*: install scripts from an egg and install egg dependencies if they
      are not already in the cache
    - *wsgi*: Make a Python paste configuration file eatable by mod_wsgi with
      all the eggs dependencies you need.

The reasons why i have rewrite yet another buildout recipe builder are:
    - Support for downloading stuff
    - Support on the fly patchs for eggs and other distribution.
    - Support multiple hooks at each stage of the build system.
    - Support for distutils
    - Robust offline mode
    - We like pypi, but offer a mode to scan for eggs without need to check
      the index.

You can browse the code on minitage's following resources:

    - http://git.minitage.org/git/minitage/eggs/minitage.recipe/
    - http://www.minitage.org/trac/browser/minitage/eggs/minitage.recipe


