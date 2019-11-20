
import unittest
import common
from common import anonymous_session, secondary_session

class CatalogBasic (common.ErmrestTest):
    def test_catalog_id(self):
        r = self.session.get('')
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(str(r.json()['id']), str(common.cid))

    def test_catalog_acl(self):
        r = self.session.get('acl')
        if self.session == common.primary_session:
            self.assertHttp(r, 200, 'application/json')
            self.assertIn('owner', r.json())
        elif self.session == secondary_session:
            # secondary user forbidden
            self.assertHttp(r, 403)
        else:
            # anonymous user asked to authenticate
            self.assertHttp(r, 401)

    def test_invalid_apiname(self):
        self.assertHttp(self.session.get('invalid_api'), 400)

class CatalogBasicOwner (CatalogBasic):
    def test_test1_schema(self):
        self.assertHttp(self.session.post('schema/test1'), 201)
        self.assertHttp(self.session.post('schema/test1'), 409)
        self.assertHttp(self.session.delete('schema/test1'), 204)
        
if anonymous_session:
    
    class CatalogBasicAnon (CatalogBasic):
        session = anonymous_session

if secondary_session:

    class CatalogBasicSecondary (CatalogBasic):
        session = secondary_session

if __name__ == '__main__':
    unittest.main(verbosity=2)
