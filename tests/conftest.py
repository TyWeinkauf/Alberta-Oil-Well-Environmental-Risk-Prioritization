"""Integration tests own only a fresh screening schema in an explicit test DB."""
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture
def test_engine():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to a separate empty database ending in _test')
    database = make_url(url).database or ''
    if not database.endswith('_test'):
        pytest.fail('Refusing integration tests: database name must end in _test')
    engine = create_engine(url)
    with engine.connect() as conn:
        exists = conn.execute(text("SELECT to_regnamespace('screening')")).scalar_one()
    if exists is not None:
        engine.dispose()
        pytest.fail('Refusing to overwrite an existing screening schema in the test database')
    try:
        yield engine
    finally:
        # Only this explicitly selected test DB's initially absent schema is ours.
        with engine.begin() as conn:
            conn.execute(text('DROP SCHEMA IF EXISTS screening CASCADE'))
        engine.dispose()
