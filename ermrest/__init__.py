
# 
# Copyright 2012-2013 University of Southern California
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

import model
import url
import exception
from catalog import Catalog

from ermrest_apis import webauthn2_manager, web_urls, registry, catalog_factory

def deploy_webauthn2():
    """
    Deploy database elements required for webauthn2.

    Uses a fully configured webauthn2.Manager instance created using
    the config in '~/ermrest_config.json' of the invoking user.

    """
    webauthn2_manager.deploy()

def webauthn2_create_user(name):
    """
    Create named user if the manager supports that.

    """
    if webauthn2_manager.clients.manage:
        webauthn2_manager.clients.manage.create_noauthz(webauthn2_manager, None, name)
    else:
        raise NotImplementedError()

def webauthn2_delete_user(name):
    """
    Delete named user if the manager supports that.

    """
    if webauthn2_manager.clients.manage:
        webauthn2_manager.clients.manage.delete_noauthz(webauthn2_manager, None, name)
    else:
        raise NotImplementedError()

def webauthn2_create_attribute(name):
    """
    Create named attribute if the manager supports that.

    """
    if webauthn2_manager.attributes.manage:
        webauthn2_manager.attributes.manage.create_noauthz(webauthn2_manager, None, name)
    else:
        raise NotImplementedError()

def webauthn2_delete_attribute(name):
    """
    Delete named attribute if the manager supports that.

    """
    if webauthn2_manager.attributes.manage:
        webauthn2_manager.attributes.manage.delete_noauthz(webauthn2_manager, None, name)
    else:
        raise NotImplementedError()

def webauthn2_set_password(username, password):
    """
    Set named user password if the manager supports that.

    """
    if webauthn2_manager.clients.passwd:
        return webauthn2_manager.clients.passwd.create_noauthz(webauthn2_manager, None, username, password)
    else:
        raise NotImplementedError()

def webauthn2_disable_password(username):
    """
    Disable named user password if the manager supports that.

    """
    if webauthn2_manager.clients.passwd:
        webauthn2_manager.clients.passwd.delete_noauthz(webauthn2_manager, None, username)
    else:
        raise NotImplementedError()

def webauthn2_assign_attribute(user, attribute):
    """
    Assign named attribute to named user if the manager supports that.

    """
    if webauthn2_manager.attributes.assign:
        webauthn2_manager.attributes.assign.create_noauthz(webauthn2_manager, None, attribute, user)
    else:
        raise NotImplementedError()

def webauthn2_unassign_attribute(user, attribute):
    """
    Unassign named attribute from named user if the manager supports that.

    """
    if webauthn2_manager.attributes.assign:
        webauthn2_manager.attributes.assign.delete_noauthz(webauthn2_manager, None, attribute, user)
    else:
        raise NotImplementedError()

def webauthn2_nest_attribute(child, parent):
    """
    Nest child attribute under parent attribute if the manager supports that.

    """
    if webauthn2_manager.attributes.nest:
        webauthn2_manager.attributes.nest.create_noauthz(webauthn2_manager, None, parent, child)
    else:
        raise NotImplementedError()

def webauthn2_unnest_attribute(child, parent):
    """
    Unnest child attribute from under parent attribute if the manager supports that.

    """
    if webauthn2_manager.attributes.nest:
        webauthn2_manager.attributes.nest.delete_noauthz(webauthn2_manager, None, parent, child)
    else:
        raise NotImplementedError()

def deploy_registry():
    """
    Deploy registry.

    Uses a fully configured registry.Registry instance created using
    the config in '~/ermrest_config.json' of the invoking user.

    """
    registry.deploy()
    
def registry_register(descriptor, id=None):
    """
    Register a catalog connection string in the ERMREST registry.
    
    Optionally, map the connection string to a specified identifier.
    
    Return the catalog identifier.
    """
    return registry.register(descriptor, id)
    
def registry_unregister(id):
    """
    Unregister a catalog from the ERMRESET registry.
    """
    registry.unregister(id)

def catalog_create():
    """
    Creates a new catalog.
    """
    catalog = catalog_factory.create()
    return catalog.descriptor

def catalog_destroy(catalog_id):
    """
    Destroys a catalog.
    """
    descriptor = registry.lookup(catalog_id)[0]['descriptor']
    catalog = Catalog(catalog_factory, descriptor)
    catalog.destroy()
    
def catalog_init_meta(catalog_id, role):
    """
    Initialize catalog metadata.
    """
    descriptor = registry.lookup(catalog_id)[0]['descriptor']
    catalog = Catalog(catalog_factory, descriptor)
    catalog.init_meta(owner=role)

def catalog_get_meta(catalog_id, key=None):
    """
    Initialize catalog metadata.
    """
    descriptor = registry.lookup(catalog_id)[0]['descriptor']
    catalog = Catalog(catalog_factory, descriptor)
    return catalog.get_meta(key)

def catalog_add_meta(catalog_id, key, value):
    """
    Initialize catalog metadata.
    """
    descriptor = registry.lookup(catalog_id)[0]['descriptor']
    catalog = Catalog(catalog_factory, descriptor)
    catalog.add_meta(key, value)

def catalog_remove_meta(catalog_id, key, value=None):
    """
    Initialize catalog metadata.
    """
    descriptor = registry.lookup(catalog_id)[0]['descriptor']
    catalog = Catalog(catalog_factory, descriptor)
    catalog.remove_meta(key, value)
