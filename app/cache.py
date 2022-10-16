from cashews import Cache

from app import config

cache = Cache(name="default")
cache.setup(config.CACHE_BACKEND_DSN)

disk_cache = Cache(name="disk")
disk_cache.setup("disk://", size_limit=config.CLIENT_CACHE_MAX_SIZE)
