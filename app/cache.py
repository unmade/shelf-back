from cashews import Cache

from app.config import config

cache = Cache(name="default")
cache.setup(config.cache.backend_dsn)

disk_cache = Cache(name="disk")
disk_cache.setup("disk://", size_limit=config.cache.disk_cache_max_size)
