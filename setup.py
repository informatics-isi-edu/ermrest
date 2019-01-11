#
# Copyright 2012-2017 University of Southern California
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

from setuptools import setup

setup(
    name='ermrest',
    description='Entity Relationship Management via REpresentational State Transfer',
    version='0.1-prerelease',
    zip_safe=False, # we need to unpack for mod_wsgi to find ermrest.wsgi 
    packages=[
        'ermrest',
        'ermrest.ermpath',
        'ermrest.exception',
        'ermrest.model',
        'ermrest.sql',
        'ermrest.url',
        'ermrest.url.ast',
        'ermrest.url.ast.data',
    ],
    package_data={
        'ermrest': ['*.wsgi', 'ermrest_config.json', 'wsgi_ermrest.conf'],
        'ermrest.sql': ['*.sql'],
    },
    scripts=[
        'sbin/ermrest-deploy',
        'sbin/ermrest-freetext-indices',
        'sbin/ermrest-registry-purge',
    ],
    #requires=['webauthn2', 'web.py', 'psycopg2'],
    maintainer_email='support@misd.isi.edu',
    license='Apache License, Version 2.0',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ])
