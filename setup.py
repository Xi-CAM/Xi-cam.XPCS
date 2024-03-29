from setuptools import setup, find_namespace_packages
from codecs import open
from os import path

__version__ = '1.3.1'

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# get the dependencies and installs
with open(path.join(here, 'requirements.txt'), encoding='utf-8') as f:
    all_reqs = f.read().split('\n')

install_requires = [x.strip() for x in all_reqs]# if 'git+' not in x]
#dependency_links = [x.strip().replace('git+', '') for x in all_reqs if x.startswith('git+')]

setup(
    name='xicam.XPCS',
    version=__version__,
    description='XPCS GUI interface',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='',
    license='BSD',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Physics',
        'Programming Language :: Python :: 3',
    ],
    keywords='',
    packages=find_namespace_packages(exclude=['docs', 'tests*']),
    package_data={'xicam.XPCS': []},
    include_package_data=True,
    author='Ron Pandolfi',
    install_requires=install_requires,
    # dependency_links=dependency_links,
    author_email='ronpandolfi@lbl.gov',
    entry_points={'xicam.plugins.GUIPlugin': ['xpcs_gui_plugin = xicam.XPCS:XPCS'],
                  'databroker.ingestors': ['application/x-hdf5 = xicam.XPCS.ingestors:ingest_nxXPCS']},
)
