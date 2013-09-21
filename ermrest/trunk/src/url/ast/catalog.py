
# 
# Copyright 2010-2013 University of Southern California
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

"""ERMREST URL abstract syntax tree (AST) classes for catalog resources.

"""
import psycopg2
from ermrest import sanepg2

import model
import data

from model import Api

class Catalogs (Api):
    """A multi-tenant catalog set."""
    pass

class Catalog (Api):
    """A specific catalog by ID."""
    def __init__(self, catalog_id):
        self.catalog_id = catalog_id

    def schemas(self):
        """The schema set for this catalog."""
        return model.Schemas(self)

    def schema(self, name):
        """A specific schema for this catalog."""
        return model.Schema(self, name)

    def entity(self, epath):
        """An entity set for this catalog."""
        return data.Entity(self, epath)

    def attribute(self, apath):
        """An attribute set for this catalog."""
        return data.Attribute(self, apath)

    def query(self, qpath):
        """An quer set for this catalog."""
        return data.Query(self, qpath)

    def get_conn(self):
        # TODO: make this smarter and safer
        return psycopg2.connect(
            database='ermrest_%d' % int(self.catalog_id),
            connection_factory=sanepg2.connection
            )


