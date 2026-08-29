from backend.main import app


def test_gzip_middleware_uses_interactive_compression_level():
    gzip_middleware = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls.__name__ == "GZipMiddleware"
    )

    assert gzip_middleware.kwargs == {"minimum_size": 1000, "compresslevel": 5}
