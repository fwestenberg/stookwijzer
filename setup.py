from distutils.core import setup
setup(
  name = 'stookwijzer',
  packages = ['stookwijzer'],
  version = '1.5.8',
  license='MIT',
  description = 'Stookwijzer package',
  long_description_content_type="text/markdown",
  long_description='Stookwijzer package',
  author = 'fwestenberg',
  author_email = '',
  url = 'https://github.com/fwestenberg/stookwijzer',
  download_url = 'https://github.com/fwestenberg/stookwijzer/releases/latest',
  keywords = ['Stookwijzer', 'Home-Assistant'],
  install_requires=[
          'aiohttp', 'pyproj', 'pytz'
      ],
  classifiers=[
    'Development Status :: 5 - Production/Stable',
    'Intended Audience :: Developers',
    'Topic :: Software Development :: Build Tools',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3.12',
    'Programming Language :: Python :: 3.13'
  ],
)
