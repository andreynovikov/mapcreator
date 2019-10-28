from urllib.parse import urlsplit, urlunsplit, quote


def iri2uri(iri: str):
    """
    Convert an IRI to a URI
    """
    try:
        (scheme, netloc, path, query, fragment) = urlsplit(iri)
    except ValueError:
        iri = iri.strip().split(' ', 1)[0]  # second try
        try:
            (scheme, netloc, path, query, fragment) = urlsplit(iri)
        except ValueError:
            return None

    scheme = quote(scheme)
    if not netloc.isascii():
        try:
            netloc = netloc.encode('idna').decode('utf-8')
        except UnicodeError:
            return None
    if path == '/':
        path = ''
    else:
        path = quote(path)
    query = quote(query)
    fragment = quote(fragment)
    return urlunsplit((scheme, netloc, path, query, fragment))
