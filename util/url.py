from urllib.parse import urlsplit, urlunsplit, quote


def iri2uri(iri):
    """
    Convert an IRI to a URI
    """
    (scheme, netloc, path, query, fragment) = urlsplit(iri)
    scheme = quote(scheme)
    if not netloc.isascii():
        netloc = netloc.encode('idna').decode('utf-8')
    if path == '/':
        path = ''
    else:
        path = quote(path)
    query = quote(query)
    fragment = quote(fragment)
    return urlunsplit((scheme, netloc, path, query, fragment))
