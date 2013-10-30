
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

"""ERMREST exception types

"""

import rest

class LexicalError (ValueError):
    """Exception for lexical errors in URL parsing"""

    def __init__(self):
        ValueError.__init__(self)
        pass

class ParseError (ValueError):
    """Exception for grammatical errors in URL parsing"""

    def __init__(self, t, message='URL parse error at token:'):
        ValueError.__init__(self, message + str(t))
        self.message = message

class UnsupportedMediaType (ValueError):
    """Exception for unsupported in_content_type."""

    def __init__(self, message=None):
        ValueError.__init__(self, message)
        self.message = message
    
class BadData (ValueError):
    """Exception for formatting errors in data inputs"""

    def __init__(self, message=None):
        ValueError.__init__(self, message)
        self.message = message

class BadSyntax (BadData):
    """Exception for invalid input syntax"""
    pass

class ConflictData (ValueError):
    """Exception for data conflicts"""

    def __init__(self, message=None):
        ValueError.__init__(self, message)
        self.message = message
        
class ConflictModel (ConflictData):
    """Exception for model conflicts, i.e. unbound table or column names"""
    pass

class NotFound (ValueError):
    """Exception for data not found"""

    def __init__(self, message=None):
        ValueError.__init__(self, message)
        self.message = message

