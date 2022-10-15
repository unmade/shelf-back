from cashews import Cache

from app import config

cache = Cache(name="default")
cache.setup(config.CACHE_BACKEND_DSN)

local_cache = Cache(name="local")
local_cache.setup("disk://")
