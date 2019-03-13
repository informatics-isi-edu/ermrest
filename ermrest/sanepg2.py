
# 
# Copyright 2013-2019 University of Southern California
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
import psycopg2.pool
import web
import sys
import traceback
import datetime
import math

class connection (psycopg2.extensions.connection):
    """Customized psycopg2 connection factory with per-execution() cursor support.

    """
    def __init__(self, dsn):
        psycopg2.extensions.connection.__init__(self, dsn)
        self._curnumber  = 1

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

def pool(minconn, maxconn, dsn):
    """Open a thread-safe connection pool with minconn <= N <= maxconn connections to database.

       The connections are from the customized connection factory in this module.
    """
    return psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, dsn=dsn, connection_factory=connection)

class PoolManager (object):
    """Manage a set of database connection pools keyed by database name.

    """
    def __init__(self):
        # map dsn -> [pool, timestamp]
        self.pools = dict()
        self.max_idle_seconds = 60 * 5 # 5 minutes

    def __getitem__(self, dsn):
        """Lookup existing or create new pool for database on demand.

           May fail transiently and caller should retry.

        """
        # abandon old pools so they can be garbage collected
        for key in list(self.pools.keys()):
            try:
                pair = self.pools.pop(key)
                delta = (datetime.datetime.now() - pair[1])
                try:
                    delta_seconds = delta.total_seconds()
                except:
                    delta_seconds = delta.seconds + delta.microseconds * math.pow(10,-6)
                    
                if delta_seconds < self.max_idle_seconds:
                    # this pool is sufficiently active so put it back!
                    boundpair = self.pools.setdefault(key, pair)
                
                if self.pools.get(key, [None])[0] != pair[0]:
                    # our pool is not registered anymore
                    pair[0].closeall()
                        
            except KeyError:
                # another thread could have purged key before we got to it
                pass

        try:
            pair = self.pools[dsn]
            pair[1] = datetime.datetime.now() # update timestamp
            return pair[0]
        except KeyError:
            # atomically get/set pool
            newpool = pool(1, 4, dsn)
            boundpair = self.pools.setdefault(dsn, [newpool, datetime.datetime.now()])
            if boundpair[0] is not newpool:
                # someone beat us to it
                newpool.closeall()
            return boundpair[0]
            

pools = PoolManager()       

class PooledConnection (object):
    def __init__(self, dsn, shared=True):
        if shared:
            self.used_pool = pools[dsn]
            self.conn = self.used_pool.getconn()
        else:
            self.used_pool = None
            self.conn = psycopg2.extensions.connection(dsn)
        self.conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE)
        self.cur = self.conn.cursor()

    def perform(self, bodyfunc, finalfunc=lambda x: x, verbose=False):
        """Run bodyfunc(conn, cur) using pooling, commit, transform with finalfunc, clean up.
        
           Automates handling of errors.
        """
        assert self.conn is not None
        try:
            result = bodyfunc(self.conn, self.cur)
            self.conn.commit()
            result = finalfunc(result)
            if hasattr(result, '__next__'):
                # need to defer cleanup to after result is drained
                for d in result:
                    yield d
            else:
                yield result
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            # reset bad connection
            if self.used_pool:
                self.used_pool.putconn(self.conn, close=True)
            self.conn = None
            raise e
        except GeneratorExit as e:
            # happens normally at end of result yielding sequence
            raise
        except:
            if self.conn is not None:
                self.conn.rollback()
            if verbose:
                et, ev, tb = sys.exc_info()
                web.debug(u'got exception "%s" during sanepg2.PooledConnection.perform()' % ev,
                          traceback.format_exception(et, ev, tb))
            raise

    def final(self):
        if self.conn is not None:
            self.cur.close()
            try:
                self.conn.commit()
            except:
                pass
            if self.used_pool:
                self.used_pool.putconn(self.conn)
            else:
                try:
                    self.conn.close()
                except:
                    pass
            self.conn = None

