
# 
# Copyright 2013 University of Southern California
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

"""Wrapper for sane access to psycopg2 with transactional data streaming.

This module provides a customized psycopg2 connection class that can
be used as a connection_factory parameter to the normal
psycopg2.connect() factory.  Also provided is a convenience pool()
factory to create a ThreadedConnectionPool that will use this
customized connection class.

The purpose of the customized connection class is to make it easier to
use a sane combination of psycopg2 features:

   1. server-side named cursors to allow streaming of large results
      without consuming lots of Python memory

   2. cursors with 'withhold=True' mode to allow results to be fetched
      before and/or after a transaction is committed

This combination allows a transaction to be committed and then to
serialize results, without any risk of commencing serialization on a
transaction that will fail nor with any need to buffer the entire
result before serialization commences.

"""

import psycopg2


class connection (psycopg2.extensions.connection):
    """Customized psycopg2 connection factory with per-execution() cursor support.

    """
    def __init__(self, dsn):
        psycopg2.extensions.connection.__init__(self, dsn)
        self._curnumber  = 1
        self._savepoints = None #TODO: Is None the right initial value?

    def execute(self, stmt, vars=None):
        """Name and create a server-side cursor with withhold=True and run statement in it.

           You can iterate over the resulting cursor to efficiently
           fetch rows from the server, and you may do this before or
           after committing the transaction.  The entire result set
           need not exist in Python memory if you dispose of your old
           rows as you go.

           Please remember to close these per-statement cursors to avoid
           wasting resources on the Postgres server session.
        """
        curname = 'cursor%d' % self._curnumber
        self._curnumber += 1
        cur = self.cursor(curname, withhold=True)
        cur.execute(stmt, vars=vars)
        return cur

def pool(minconn, maxconn, database):
    """Open a thread-safe connection pool with minconn <= N <= maxconn connections to database.

       The connections are from the customized connection factory in this module.
    """
    return psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, database=database, connection_factory=connection)

