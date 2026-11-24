import pytest

from src.artifacts import write_json


def test_failed_serialization_cleans_temporary_file_and_preserves_previous_artifact(tmp_path):
    destination = tmp_path / 'manifest.json'
    write_json(destination, {'status': 'previous'})
    original = destination.read_bytes()

    with pytest.raises(TypeError):
        write_json(destination, {'unserializable': object()})

    assert destination.read_bytes() == original
    assert list(tmp_path.iterdir()) == [destination]
