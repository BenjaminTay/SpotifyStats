import pytest


@pytest.mark.parametrize(
    "path",
    (
        "/api/billboard/track/1",
        "/api/billboard/album/Test%20Album",
        "/api/billboard/artist/Test%20Artist",
    ),
)
def test_billboard_detail_rejects_unsupported_view(client, path):
    response = client.get(path, params={"view": "unsupported"})

    assert response.status_code == 422
