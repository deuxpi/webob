from webob import Request
from webob.request import NoDefault, BaseRequest
from webtest import TestApp
from nose.tools import eq_, ok_, assert_raises, raises
from cStringIO import StringIO

def simpleapp(environ, start_response):
    status = '200 OK'
    response_headers = [('Content-type','text/plain')]
    start_response(status, response_headers)
    request = Request(environ)
    request.remote_user = 'bob'
    return [
        'Hello world!\n',
        'The get is %r' % request.str_GET,
        ' and Val is %s\n' % request.str_GET.get('name'),
        'The languages are: %s\n' % request.accept_language.best_matches('en-US'),
        'The accepttypes is: %s\n' % request.accept.best_match(['application/xml', 'text/html']),
        'post is %r\n' % request.str_POST,
        'params is %r\n' % request.str_params,
        'cookies is %r\n' % request.str_cookies,
        'body: %r\n' % request.body,
        'method: %s\n' % request.method,
        'remote_user: %r\n' % request.environ['REMOTE_USER'],
        'host_url: %r; application_url: %r; path_url: %r; url: %r\n' % (request.host_url, request.application_url, request.path_url, request.url),
        'urlvars: %r\n' % request.urlvars,
        'urlargs: %r\n' % (request.urlargs, ),
        'is_xhr: %r\n' % request.is_xhr,
        'if_modified_since: %r\n' % request.if_modified_since,
        'user_agent: %r\n' % request.user_agent,
        'if_none_match: %r\n' % request.if_none_match,
        ]

def test_gets():
    app = TestApp(simpleapp)
    res = app.get('/')
    assert 'Hello' in res
    assert "get is GET([])" in res
    assert "post is <NoVars: Not a form request>" in res

    res = app.get('/?name=george')
    res.mustcontain("get is GET([('name', 'george')])")
    res.mustcontain("Val is george")

def test_language_parsing():
    app = TestApp(simpleapp)
    res = app.get('/')
    assert "The languages are: ['en-US']" in res

    res = app.get('/', headers={'Accept-Language':'da, en-gb;q=0.8, en;q=0.7'})
    assert "languages are: ['da', 'en-gb', 'en-US']" in res

    res = app.get('/', headers={'Accept-Language':'en-gb;q=0.8, da, en;q=0.7'})
    assert "languages are: ['da', 'en-gb', 'en-US']" in res

def test_mime_parsing():
    app = TestApp(simpleapp)
    res = app.get('/', headers={'Accept':'text/html'})
    assert "accepttypes is: text/html" in res

    res = app.get('/', headers={'Accept':'application/xml'})
    assert "accepttypes is: application/xml" in res

    res = app.get('/', headers={'Accept':'application/xml,*/*'})
    assert "accepttypes is: application/xml" in res, res


def test_accept_best_match():
    assert not Request.blank('/').accept
    assert not Request.blank('/', headers={'Accept': ''}).accept
    req = Request.blank('/', headers={'Accept':'text/plain'})
    ok_(req.accept)
    assert_raises(ValueError, req.accept.best_match, ['*/*'])
    req = Request.blank('/', accept=['*/*','text/*'])
    eq_(req.accept.best_match(['application/x-foo', 'text/plain']), 'text/plain')
    eq_(req.accept.best_match(['text/plain', 'application/x-foo']), 'text/plain')
    req = Request.blank('/', accept=['text/plain', 'message/*'])
    eq_(req.accept.best_match(['message/x-foo', 'text/plain']), 'text/plain')
    eq_(req.accept.best_match(['text/plain', 'message/x-foo']), 'text/plain')

def test_from_mimeparse():
    # http://mimeparse.googlecode.com/svn/trunk/mimeparse.py
    supported = ['application/xbel+xml', 'application/xml']
    tests = [('application/xbel+xml', 'application/xbel+xml'),
             ('application/xbel+xml; q=1', 'application/xbel+xml'),
             ('application/xml; q=1', 'application/xml'),
             ('application/*; q=1', 'application/xbel+xml'),
             ('*/*', 'application/xbel+xml')]

    for accept, get in tests:
        req = Request.blank('/', headers={'Accept':accept})
        assert req.accept.best_match(supported) == get, (
            '%r generated %r instead of %r for %r' % (accept, req.accept.best_match(supported), get, supported))

    supported = ['application/xbel+xml', 'text/xml']
    tests = [('text/*;q=0.5,*/*; q=0.1', 'text/xml'),
             ('text/html,application/atom+xml; q=0.9', None)]

    for accept, get in tests:
        req = Request.blank('/', headers={'Accept':accept})
        assert req.accept.best_match(supported) == get, (
            'Got %r instead of %r for %r' % (req.accept.best_match(supported), get, supported))

    supported = ['application/json', 'text/html']
    tests = [('application/json, text/javascript, */*', 'application/json'),
             ('application/json, text/html;q=0.9', 'application/json')]

    for accept, get in tests:
        req = Request.blank('/', headers={'Accept':accept})
        assert req.accept.best_match(supported) == get, (
            '%r generated %r instead of %r for %r' % (accept, req.accept.best_match(supported), get, supported))

    offered = ['image/png', 'application/xml']
    tests = [
        ('image/png', 'image/png'),
        ('image/*', 'image/png'),
        ('image/*, application/xml', 'application/xml'),
    ]

    for accept, get in tests:
        req = Request.blank('/', accept=accept)
        eq_(req.accept.best_match(offered), get)

def test_headers():
    app = TestApp(simpleapp)
    headers = {
        'If-Modified-Since': 'Sat, 29 Oct 1994 19:43:31 GMT',
        'Cookie': 'var1=value1',
        'User-Agent': 'Mozilla 4.0 (compatible; MSIE)',
        'If-None-Match': '"etag001", "etag002"',
        'X-Requested-With': 'XMLHttpRequest',
        }
    res = app.get('/?foo=bar&baz', headers=headers)
    res.mustcontain(
        'if_modified_since: datetime.datetime(1994, 10, 29, 19, 43, 31, tzinfo=UTC)',
        "user_agent: 'Mozilla",
        'is_xhr: True',
        "cookies is {'var1': 'value1'}",
        "params is NestedMultiDict([('foo', 'bar'), ('baz', '')])",
        "if_none_match: <ETag etag001 or etag002>",
        )

def test_bad_cookie():
    req = Request.blank('/')
    req.headers['Cookie'] = '070-it-:><?0'
    assert req.cookies == {}
    req.headers['Cookie'] = 'foo=bar'
    assert req.cookies == {'foo': 'bar'}
    req.headers['Cookie'] = '...'
    assert req.cookies == {}
    req.headers['Cookie'] = '=foo'
    assert req.cookies == {}
    req.headers['Cookie'] = 'dismiss-top=6; CP=null*; PHPSESSID=0a539d42abc001cdc762809248d4beed; a=42'
    eq_(req.cookies, {
        'CP':           u'null*',
        'PHPSESSID':    u'0a539d42abc001cdc762809248d4beed',
        'a':            u'42',
        'dismiss-top':  u'6'
    })
    req.headers['Cookie'] = 'fo234{=bar blub=Blah'
    assert req.cookies == {'blub': 'Blah'}

def test_cookie_quoting():
    req = Request.blank('/')
    req.headers['Cookie'] = 'foo="?foo"; Path=/'
    assert req.cookies == {'foo': '?foo'}

def test_params():
    req = Request.blank('/?a=1&b=2')
    req.method = 'POST'
    req.body = 'b=3'
    assert req.params.items() == [('a', '1'), ('b', '2'), ('b', '3')]
    new_params = req.params.copy()
    assert new_params.items() == [('a', '1'), ('b', '2'), ('b', '3')]
    new_params['b'] = '4'
    assert new_params.items() == [('a', '1'), ('b', '4')]
    # The key name is \u1000:
    req = Request.blank('/?%E1%80%80=x', decode_param_names=True, charset='UTF-8')
    assert req.decode_param_names
    assert u'\u1000' in req.GET.keys()
    assert req.GET[u'\u1000'] == 'x'

class UnseekableInput(object):
    def __init__(self, data):
        self.data = data
        self.pos = 0
    def read(self, size=-1):
        if size == -1:
            t = self.data[self.pos:]
            self.pos = len(self.data)
            return t
        else:
            assert self.pos + size <= len(self.data), (
                "Attempt to read past end (length=%s, position=%s, reading %s bytes)"
                % (len(self.data), self.pos, size))
            t = self.data[self.pos:self.pos+size]
            self.pos += size
            return t

def test_copy_body():
    req = Request.blank('/', method='POST', body='some text', request_body_tempfile_limit=1)
    old_body_file = req.body_file
    req.copy_body()
    assert req.body_file is not old_body_file
    req = Request.blank('/', method='POST', body_file=UnseekableInput('0123456789'), content_length=10)
    assert not hasattr(req.body_file, 'seek')
    old_body_file = req.body_file
    req.make_body_seekable()
    assert req.body_file is not old_body_file
    assert req.body == '0123456789'
    old_body_file = req.body_file
    req.make_body_seekable()
    assert req.body_file is old_body_file

def test_broken_clen_header():
    # if the UA sends "content_length: ..' header (the name is wrong)
    # it should not break the req.headers.items()
    req = Request.blank('/')
    req.environ['HTTP_CONTENT_LENGTH'] = '0'
    req.headers.items()

def test_nonstr_keys():
    # non-string env keys shouldn't break req.headers
    req = Request.blank('/')
    req.environ[1] = 1
    req.headers.items()


def test_authorization():
    req = Request.blank('/')
    req.authorization = 'Digest uri="/?a=b"'
    assert req.authorization == ('Digest', {'uri': '/?a=b'})

def test_authorization2():
    from webob.descriptors import parse_auth_params
    for s, d in [
       ('x=y', {'x': 'y'}),
       ('x="y"', {'x': 'y'}),
       ('x=y,z=z', {'x': 'y', 'z': 'z'}),
       ('x=y, z=z', {'x': 'y', 'z': 'z'}),
       ('x="y",z=z', {'x': 'y', 'z': 'z'}),
       ('x="y", z=z', {'x': 'y', 'z': 'z'}),
       ('x="y,x", z=z', {'x': 'y,x', 'z': 'z'}),
    ]:
        eq_(parse_auth_params(s), d)

def test_from_file():
    req = Request.blank('http://example.com:8000/test.html?params')
    equal_req(req)

    req = Request.blank('http://example.com/test2')
    req.method = 'POST'
    req.body = 'test=example'
    equal_req(req)

def equal_req(req):
    input = StringIO(str(req))
    req2 = Request.from_file(input)
    eq_(req.url, req2.url)
    headers1 = dict(req.headers)
    headers2 = dict(req2.headers)
    eq_(int(headers1.get('Content-Length', '0')),
        int(headers2.get('Content-Length', '0')))
    if 'Content-Length' in headers1:
        del headers1['Content-Length']
    if 'Content-Length' in headers2:
        del headers2['Content-Length']
    eq_(headers1, headers2)
    eq_(req.body, req2.body)

def test_req_kw_none_val():
    assert 'content-length' not in Request({}, content_length=None).headers
    assert 'content-type' not in Request({}, content_type=None).headers

def test_repr_nodefault():
    nd = NoDefault
    eq_(repr(nd), '(No Default)')

@raises(TypeError)
def test_request_noenviron_param():
    Request(environ=None)

@raises(ValueError)
def test_environ_getter():
    """
    Parameter environ_getter in Request is no longer valid and should raise
    an error in case it's used
    """
    class env(object):
        def __init__(self, env):
            self.env = env
        def env_getter(self):
            return self.env
    Request(environ_getter=env({'a':1}).env_getter)

def test_unicode_errors():
    """
    Passing unicode_errors != NoDefault should assign value to
    dictionary['unicode_errors'], else not
    """
    r = Request({'a':1}, unicode_errors='strict')
    ok_('unicode_errors' in r.__dict__)
    r = Request({'a':1}, unicode_errors=NoDefault)
    ok_('unicode_errors' not in r.__dict__)

@raises(DeprecationWarning)
def test_charset_deprecation1():
    """
    Any class that inherits from BaseRequest cannot define a default_charset
    attribute
    """
    class NewRequest(BaseRequest):
        default_charset = 'utf-8'
        def __init__(self, environ, **kw):
            super(NewRequest, self).__init__(environ, **kw) 
    r = NewRequest({'a':1})

@raises(DeprecationWarning)
def test_charset_deprecation2():
    """
    Any class that inherits from BaseRequest cannot define a charset attr
    that is instance of str
    """
    class NewRequest(BaseRequest):
        charset = 'utf-8'
        def __init__(self, environ, **kw):
            super(NewRequest, self).__init__(environ, **kw) 
    r = NewRequest({'a':1})

@raises(TypeError)
def test_unexpected_kw():
    """
    Passed an attr in kw that does not exist in the class, should raise an
    error
    """
    r = Request({'a':1}, **{'this_does_not_exist':1})

def test_expected_kw():
    """Passed an attr in kw that does exist in the class, should be ok"""
    r = Request({'a':1}, **{'charset':'utf-8', 'server_name':'127.0.0.1'}) 
    eq_(getattr(r, 'charset', None), 'utf-8')
    eq_(getattr(r, 'server_name', None), '127.0.0.1')

def test_body_file_setter():
    """"
    If body_file is passed and it's instance of str, we define
    environ['wsgi.input'] and content_length. Plus, while deleting the
    attribute, we should get '' and 0 respectively
    """
    r = Request({'a':1}, **{'body_file':'hello world'}) 
    eq_(r.environ['wsgi.input'].getvalue(), 'hello world')
    eq_(int(r.environ['CONTENT_LENGTH']), len('hello world'))
    del r.body_file
    eq_(r.environ['wsgi.input'].getvalue(), '')
    eq_(int(r.environ['CONTENT_LENGTH']), 0)
