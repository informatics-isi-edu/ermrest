
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

# TODO: figure out where to do this stuff...
#from ermrest import webauthn2_handler_factory, WsgiDispatcher

UserSession = webauthn2_handler_factory.UserSession
UserPassword = webauthn2_handler_factory.UserPassword
UserManage = webauthn2_handler_factory.UserManage
AttrManage = webauthn2_handler_factory.AttrManage
AttrAssign = webauthn2_handler_factory.AttrAssign
AttrNest = webauthn2_handler_factory.AttrNest

web_urls = (
    # user authentication via webauthn2
    '/authn/session(/[^/]+)', UserSession,
    '/authn/session/?()', UserSession,
    '/authn/password(/[^/]+)', UserPassword,
    '/authn/password/?()', UserPassword,

    # user account management via webauthn2
    '/authn/user(/[^/]+)', UserManage,
    '/authn/user/?()', UserManage,
    '/authn/attribute(/[^/]+)', AttrManage,
    '/authn/attribute/?()', AttrManage,
    '/authn/user/([^/]+)/attribute(/[^/]+)', AttrAssign,
    '/authn/user/([^/]+)/attribute/?()', AttrAssign,
    '/authn/attribute/([^/]+)/implies(/[^/]+)', AttrNest,
    '/authn/attribute/([^/]+)/implies/?()', AttrNest,

    # core parser-based REST dispatcher
    '.*', 'WsgiDispatcher'
)


