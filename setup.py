from setuptools import setup

def get_version():
    from os.path import dirname, join
    for line in open (join (dirname (__file__), 'gif.py')):
        if '__version__' in line:
            return line.split("'")[1]

setup(
    name             = 'pygif',
    version          = get_version (),
    author           = 'Robert Ancell',
    author_email     = 'robert.ancell@ubuntu.com',
    description      = 'Pure Python GIF image encoder/decoder',
    license          = 'LGPL-3',
    url              = 'https://github.com/robert-ancell/pygif',
    py_modules       = [ 'gif' ],
    classifiers      = [ 'Topic :: Multimedia :: Graphics',
                         'Topic :: Software Development :: Libraries :: Python Modules',
                         'Programming Language :: Python',
                         'Programming Language :: Python :: 3',
                         'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
                         'Operating System :: OS Independent' ] )
