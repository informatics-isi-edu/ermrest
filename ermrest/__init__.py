
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

import pkgutil
import sys
import os.path

def sample_config():
    """Emit sample ermrest_config.json to standard output."""
    sys.stdout.write(pkgutil.get_data(__name__, 'ermrest_config.json'))

def sample_httpd_config():
    """Emit sample wsgi_ermrest.conf to standard output."""
    path = __path__[0]
    if path[0] != '/':
        loader = pkgutil.get_loader('ermrest')
        path = '%s/%s' % (
            os.path.dirname(loader.get_filename('ermrest'),
            path
        )
    sys.stdout.write(
        pkgutil.get_data(__name__, 'wsgi_ermrest.conf').replace(
            '/usr/lib/python2.7/site-packages/ermrest',
            path
        )
    )
