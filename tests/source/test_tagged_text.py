from papaya.source import TaggedText


def test_parse_tagged_text():
    tagged = TaggedText.parse('foobar|n=1&xywh=123,456,789,789')
    assert tagged.text == 'foobar'
    assert tagged.params == {'n': '1', 'xywh': '123,456,789,789'}
