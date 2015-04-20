#
# Copyright 2012 University of Southern California
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from distutils.core import setup

setup(
    name='ermrest',
    description='Entity Relationship Management via REpresentational State Transfer',
    version='0.1-prerelease',
    package_dir={'ermrest': 'src'},
    packages=['ermrest', 'ermrest.exception', 'ermrest.url', 'ermrest.url.ast', 'ermrest.url.ast.data'],
    install_requires=['webauthn2', 'web.py', 'psycopg2', 'simplejson', 'python-dateutil'],
    maintainer_email='support@misd.isi.edu',
    license='Apache License, Version 2.0',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ])
