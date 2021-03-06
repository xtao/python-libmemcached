import sys
from zlib import compress, decompress, error as zlib_error
from cmemcached_imp import *
import cmemcached_imp 

_FLAG_PICKLE = 1<<0
_FLAG_INTEGER = 1<<1
_FLAG_LONG = 1<<2
_FLAG_BOOL = 1<<3
_FLAG_COMPRESS = 1<<4
_FLAG_MARSHAL = 1<<5

VERSION="0.40"

def prepare(val, comp_threshold):
    val, flag = cmemcached_imp.prepare(val)
    if comp_threshold > 0 and val and len(val) > comp_threshold:
        val = compress(val)
        flag |= _FLAG_COMPRESS
    return val, flag

def restore(val, flag):
    if val is None:
        return val

    if flag & _FLAG_COMPRESS:
        try:
            val = decompress(val)
        except zlib_error:
            return None
        flag &= ~_FLAG_COMPRESS

    return cmemcached_imp.restore(val, flag)

class Client(cmemcached_imp.Client):
    "a wraper around cmemcached_imp"

    def __init__(self, servers, do_split=1, comp_threshold=0, behaviors={}, *a, **kw):
        cmemcached_imp.Client.__init__(self)
        self.servers = servers
        self.do_split = do_split
        self.comp_threshold = comp_threshold
        self.behaviors = dict(behaviors.items())
        self.add_server(servers)
        
        self.set_behavior(BEHAVIOR_NO_BLOCK, 1) # nonblock
        self.set_behavior(BEHAVIOR_TCP_NODELAY, 1) # nonblock
        self.set_behavior(BEHAVIOR_TCP_KEEPALIVE, 1)
        self.set_behavior(BEHAVIOR_CACHE_LOOKUPS, 1)
        #self.set_behavior(BEHAVIOR_BUFFER_REQUESTS, 0) # no request buffer
        
        #self.set_behavior(BEHAVIOR_KETAMA, 1)
        self.set_behavior(BEHAVIOR_HASH, HASH_MD5)
        self.set_behavior(BEHAVIOR_KETAMA_HASH, HASH_MD5)
        self.set_behavior(BEHAVIOR_DISTRIBUTION, DIST_CONSISTENT_KETAMA)

        for k,v in behaviors.items():
            self.set_behavior(k, v)

    def __reduce__(self):
        return (Client, (self.servers, self.do_split, self.comp_threshold, self.behaviors))

    def set_behavior(self, k, v):
        self.behaviors[k] = v
        return cmemcached_imp.Client.set_behavior(self, k, v)

    def set(self, key, val, time=0, compress=True):
        comp = compress and self.comp_threshold or 0
        val, flag = prepare(val, comp)
        if val is not None:
            return self.set_raw(key, val, time, flag)
        else:
            print >>sys.stderr, '[cmemcached]', 'serialize %s failed' % key

    def set_multi(self, values, time=0, compress=True):
        comp = compress and self.comp_threshold or 0
        raw_values = dict((k, prepare(v, comp)) for k,v in values.iteritems())
        return self.set_multi_raw(raw_values, time)

    def get(self, key):
        val, flag = cmemcached_imp.Client.get_raw(self, key)
        return restore(val, flag)

    def get_multi(self, keys):
        result = cmemcached_imp.Client.get_multi_raw(self, keys)
        return dict((k, restore(v, flag))
                    for k, (v, flag) in result.iteritems())

    def get_list(self, keys):
        result = self.get_multi(keys)
        return [result.get(key) for key in keys]

    def expire(self, key):
        return self.touch(key, -1)
