import pytest

from papaya.source import format_language_tags


@pytest.mark.parametrize(
    ('values', 'expected'),
    [
        ([], []),
        (['simple'], ['simple']),
        (['[@de]der Hund'], [{'@language': 'de', '@value': 'der Hund'}]),
        (['[@de]der Hund', 'simple'], [{'@language': 'de', '@value': 'der Hund'}, 'simple']),
    ]
)
def test_format_language_tags(values, expected):
    assert list(format_language_tags(values)) == expected
