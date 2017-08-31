
import unittest
import common
from common import catalog_initial_version

class CatalogHistory (common.ErmrestTest):
    container_resource = ''
    annotation_resource = 'annotation'
    
    latest = None
    earliest = catalog_initial_version

    @classmethod
    def setUpClass(cls):
        # make sure catalog version is higher now
        common.primary_session.put(
            '%s/HISTORY' % cls.annotation_resource,
            json=cls.container_resource
        ).raise_for_status()
        # bootstrap catalog version info
        r = common.primary_session.get('')
        r.raise_for_status()
        cls.latest = r.json()['version']

    def test_at_latest(self):
        r = self.session.get((self.latest, self.container_resource))
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(self.latest, r.json()['version'])
        return r

    def test_at_earliest(self):
        r = self.session.get((self.earliest, self.container_resource))
        self.assertHttp(r, 200, 'application/json')
        self.assertEqual(self.earliest, r.json()['version'])
        return r

class ModelHistory (CatalogHistory):
    container_resource = 'schema'
    
    def test_annotation_at_latest(self):
        r = self.test_at_latest()
        self.assertIn('HISTORY', r.json()['annotations'])

    def test_annotation_at_earliest(self):
        r = self.test_at_earliest()
        self.assertNotIn('HISTORY', r.json()['annotations'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
