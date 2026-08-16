from coverage_acquisition.mvt_decoder import feature_rows_from_decoded_tile


def test_configured_mvt_layer_excludes_background_features():
    decoded_tile = {
        "water": {
            "extent": 4096,
            "feature_count": 1,
            "features": [
                {
                    "id": 1,
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {},
                }
            ],
        },
        "overview": {
            "extent": 4096,
            "feature_count": 1,
            "features": [
                {
                    "id": 2,
                    "geometry": {"type": "Point", "coordinates": [1, 1]},
                    "properties": {},
                }
            ],
        },
    }

    rows, layer_counts = feature_rows_from_decoded_tile(
        decoded_tile=decoded_tile,
        provider="mapillary",
        source_id="mapillary_mly1_public_vtp",
        display_zoom=5,
        source_zoom=5,
        tile_x=0,
        tile_y=0,
        tile_url="",
        fetched_at="",
        include_layers=("overview",),
    )

    assert layer_counts == {"overview": 1}
    assert len(rows) == 1
    assert rows[0]["layer_name"] == "overview"
