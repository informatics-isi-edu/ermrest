
import unittest

import os
import sys
import platform
import atexit

import requests
import cookielib
from cookielib import IPV4_RE

import io
import csv
import json
import urllib

#import logging
#logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
#cookielib.debug = True

_scheme = os.getenv('TEST_SCHEME', 'https')
_server = os.getenv('TEST_HOSTNAME', platform.uname()[1])
_server_url = "%s://%s" % (_scheme, _server)

if os.getenv('TEST_SSL_VERIFY', 'true').lower() == 'false':
    _verify = False
else:
    _verify = True

# this will be the dynamically generated catalog ID and corresponding path
cid = None
cpath = None

def dump_cookies(cookies, preamble):
    sys.stderr.write(preamble)
    for c in cookies:
        sys.stderr.write('  %r\n' % c)
    sys.stderr.write('end\n')
            
class TestSession (requests.Session):
    """Our extended version of requests.Session for test client stubs.

       We have a built-in idea of the server and catalog URL and
       override all the testing HTTP methods to supply a bare path and
       prepend these to get a full URL for each access.

       An absolute path e.g. "/ermrest" will be appended to the bare
       server URL.

       A relative path e.g. "schema" will be appended to the catalog
       URL.

    """

    def _test_mount(self, cookiefilename=None, reportname=None):
        """Mount the statically configured test server, configure a cookiestore."""
        requests.Session.mount(
            self, _server_url + '/',
            requests.adapters.HTTPAdapter(max_retries=5)
        )

        self.verify = _verify
    
        if cookiefilename:
            cj = cookielib.MozillaCookieJar(cookiefilename)
            cj.load(ignore_expires=True)
            for cookie in cj:
                kwargs={
                    "domain": cookie.domain,
                    "path": cookie.path,
                }
                if cookie.domain.find('.') == -1 and not IPV4_RE.search(cookie.domain):
                    # mangle this the same way cookielib does or domain matching will fail!
                    kwargs['domain'] = cookie.domain + '.local'
                if cookie.expires:
                    kwargs['expires'] = cookie.expires
                
                self.cookies.set(
                    cookie.name,
                    cookie.value,
                    **kwargs
                )

        if reportname:
            dump_cookies(
                self.cookies,
                ('Created %s' + (' with cookies %s:\n' % cookiefilename if cookiefilename else '\n')) % reportname
            )

    def _path2url(self, path):
        if path == '' or path[0] != '/':
            path = "%s/%s" % (cpath, path)
        return _server_url + path

    def get_client_id(self):
        r = self.get('/authn/session')
        if r.status_code == 200:
            return r.json()["client"]["id"]
        else:
            return None
    
    def head(self, path, **kwargs):
        return requests.Session.head(self, self._path2url(path), **kwargs)

    def get(self, path, **kwargs):
        return requests.Session.get(self, self._path2url(path), **kwargs)

    def _fixup_kwargs(self, kwargs):
        if 'json' in kwargs and kwargs['json'] is None and 'data' not in kwargs:
            kwargs['data'] = 'null'
            kwargs['headers'] = dict(kwargs.get('headers', {}))
            kwargs['headers'].update({'content-type': 'application/json'})
    
    def put(self, path, **kwargs):
        self._fixup_kwargs(kwargs)
        return requests.Session.put(self, self._path2url(path), **kwargs)

    def post(self, path, **kwargs):
        self._fixup_kwargs(kwargs)
        return requests.Session.post(self, self._path2url(path), **kwargs)

    def delete(self, path, **kwargs):
        return requests.Session.delete(self, self._path2url(path), **kwargs)

# setup the primary session (privileged user)
primary_session = TestSession()
_primary_cookies = os.getenv('TEST_COOKIES1')
assert _primary_cookies, "TEST_COOKIES1 must be a cookie file name"
primary_session._test_mount(_primary_cookies, 'primary session')
primary_client_id = primary_session.get_client_id()
sys.stderr.write('Using primary_session with client ID %r.\n' % primary_client_id)

# setup the secondary session (less privileged user) if possible
secondary_session = TestSession()
_secondary_cookies = os.getenv('TEST_COOKIES2')
if _secondary_cookies:
    secondary_session._test_mount(_secondary_cookies, 'secondary session')
    secondary_client_id = secondary_session.get_client_id()
    assert primary_client_id != secondary_client_id, "TEST_COOKIES1 and TEST_COOKIES2 must provide distinct client IDs"
    sys.stderr.write('Using secondary_session with client ID %r.\n' % secondary_client_id)
else:
    sys.stderr.write('Disabling secondary_session due to missing TEST_COOKIES2.\n\n')
    secondary_session = None
    secondary_client_id = None

catalog_acls = {
    # owner is defaulted
    "write": [],
    "insert": [],
    "update": [],
    "delete": [],
    "select": [],
    "create": [],
    "enumerate": ["*"]
}
    
sys.stderr.write('Creating test catalog... ')
try:
    _r = primary_session.post('/ermrest/catalog')
    _r.raise_for_status()
    cid = _r.json()['id']
    cpath = "/ermrest/catalog/%s" % cid
    primary_session.put('acl', json=catalog_acls).raise_for_status()
    sys.stderr.write('OK.\n\n')
except Exception, e:
    sys.stderr.write('ERROR: %s.\n\n' % e)
    sys.stderr.write('REQUEST: %r %r\n%r\n\n\nRESPONSE: %r\n%r\n%r\n' % (
        _r.request.method,
        _r.request.url,
        _r.request.headers,
        _r.status_code,
        _r.headers,
        _r.content
    ))
    raise e

# setup the anonymous session (no authentication) if possible
anonymous_session = TestSession()
anonymous_session._test_mount(reportname='anonymous session')
try:
    anonymous_session.get('').raise_for_status()
except Exception, e:
    sys.stderr.write('Disabling anonymous_session due to error: %s\n\n' % e)
    anonymous_session = None

@atexit.register
def _cleanup():
    if cid is not None:
        sys.stderr.write('\nOn exit, deleting %s... ' % cpath)
        r = primary_session.delete(cpath)
        try:
            r.raise_for_status()
            sys.stderr.write('OK.\n')
        except Exception, e:
            sys.stderr.write('ERROR: %s.\n' % e)

class ErmrestTest (unittest.TestCase):
    session = primary_session

    def assertJsonEqual(self, actual, expected):
        if type(expected) in (str, unicode):
            self.assertIn(type(actual), (str, unicode))
        else:
            self.assertIsInstance(actual, type(expected))
        if type(actual) is list:
            self.assertEqual(len(actual), len(expected))
            for i in range(len(actual)):
                self.assertJsonEqual(actual[i], expected[i])
        elif type(actual) is dict:
            self.assertEqual(set(actual.keys()), set(expected.keys()))
            for k in actual.keys():
                self.assertJsonEqual(actual[k], expected[k])
        else:
            self.assertEqual(actual, expected)
        
    def assertHttp(self, r, status=200, content_type=None, hdrs={}):
        try:
            if status is None:
                pass
            elif type(status) is int:
                self.assertEqual(r.status_code, status)
            else:
                self.assertIn(r.status_code, status)
            if content_type is None:
                pass
            elif type(content_type) in (str, unicode):
                self.assertEqual(r.headers.get('content-type')[0:len(content_type)], content_type)
            else:
                self.assertIn(r.headers.get('content-type'), content_type)
                self.assertDictContainsSubset(hdrs, r.headers)
        except:
            sys.stderr.write('\n%s\n%s\n%s\n%s\n%s\n\n' % (
                r.request,
                r.request.body,
                r.status_code,
                r.headers,
                r.content
                ))
            raise
                    
def array_to_csv(a, json_array=False):
    assert type(a) is list
    keys = set()
    for row in a:
        keys.update(set(row.keys()))
    keys = list(keys)

    def wrap(v):
        if v is None:
            return ''
        elif type(v) is dict:
            return json.dumps(v)
        elif type(v) is list:
            if json_array:
                return json.dumps(v)
            else:
                return '{%s}' % (','.join([
                    '"%s"' % wrap(x).replace('"', '\\"') for x in v
                ]))
        else:
            return "%s" % v
    
    output = io.BytesIO()
    writer = csv.writer(output)
    writer.writerow(keys)
    for row in a:
        writer.writerow([ wrap(row[k]) for k in keys ])
    return output.getvalue()
    
def urlquote(s):
    return urllib.quote(s, safe="")
