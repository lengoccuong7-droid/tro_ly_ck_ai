import time

class CacheManager:
    def __init__(self, default_ttl: int = 900): # 900 giây = 15 phút
        self._cache = {}
        self.default_ttl = default_ttl

    def get(self, key: str):
        """Lấy dữ liệu từ cache nếu chưa hết hạn."""
        if key in self._cache:
            data, timestamp, ttl = self._cache[key]
            if time.time() - timestamp < ttl:
                return data
            else:
                del self._cache[key] # Xóa nếu đã hết hạn
        return None

    def set(self, key: str, value: any, ttl: int = None):
        """Lưu dữ liệu vào cache với thời gian sống (TTL)."""
        ttl = ttl if ttl is not None else self.default_ttl
        self._cache[key] = (value, time.time(), ttl)

    def clear(self):
        """Xóa sạch bộ nhớ đệm."""
        self._cache.clear()

