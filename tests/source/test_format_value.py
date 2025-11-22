import pytest

from papaya.source import format_value


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('untagged', 'untagged'),
        ('[@de]der Hund', {'@language': 'de', '@value': 'der Hund'}),
    ],
)
def test_format_value(value, expected):
    assert format_value(value) == expected
