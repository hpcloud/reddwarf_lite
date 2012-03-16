# Copyright 2012 HP Software, LLC
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

__author__ = 'dragosmanolescu'
__email__ = 'dragosm@hp.com'
__python_version__ = '2.7.2'


class Singleton:
    """
    Singleton implementation via decorators. Not thread-safe ;)
    """
    def __init__(self, the_class):
        self.the_class = the_class
        self.instance = None

    def __call__(self, *args, **kwargs):
        if self.instance is None:
            self.instance = self.the_class(*args, **kwargs)
        return self.instance


def main():
    """
    Example/test showing how to use the @Singleton decorator
    """

    @Singleton
    class Test:
        def __init__(self, arg, arg1='k1'):
            self.arg = arg
            self.arg1 = arg1

        def values(self):
            return self.arg, self.arg1

    t1 = Test('a')
    t2 = Test('b', arg1=2)
    assert(t1.values() == t2.values())

if __name__ == '__main__':
    main()
