
# 
# Copyright 2012-2023 University of Southern California
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
    sys.stdout.write(pkgutil.get_data(__name__, 'ermrest_config.json').decode())

def sample_httpd_config():
    """Emit sample wsgi_ermrest.conf to standard output."""
    path = __path__[0]
    if path[0] != '/':
        path = '%s/%s' % (
            os.path.dirname(loader.get_filename('ermrest')),
            path
        )
    sys.stdout.write(
        """
# this file must be loaded (alphabetically) after wsgi.conf
AllowEncodedSlashes On

WSGIPythonOptimize 1
WSGIDaemonProcess ermrest processes=1 threads=4 user=ermrest maximum-requests=2000
# adjust this to your ermrest package install installation
# e.g. python3 -c 'import distutils.sysconfig;print(distutils.sysconfig.get_python_lib())'
WSGIScriptAlias /ermrest %(ermrest_location)s/ermrest.wsgi process-group=ermrest
WSGIPassAuthorization On

# adjust this to your Apache wsgi socket prefix
WSGISocketPrefix /var/run/httpd/wsgi

<Location "/ermrest" >
   AuthType none
   Require all granted
   #AuthType webauthn
   #Require webauthn-optional
   WSGIProcessGroup ermrest

   # site can disable redundant service logging by adding env=!dontlog to their CustomLog or similar directives
   SetEnv dontlog
</Location>
""" % {
    'ermrest_location': path,
}
    )
