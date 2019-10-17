"""
PySmaz a Python port of the SMAZ short string text compression library.
Python port by Max Smith
Smaz by Salvatore Sanfilippo

BSD license per original C implementation at https://github.com/antirez/smaz

CREDITS
-------
Small was written by Salvatore Sanfilippo and is released under the BSD license. See __License__ section for more
information
"""

__author__ = "Salvatore Sanfilippo and Max Smith"
__copyright__ = "Copyright 2006-2014 Max Smith, Salvatore Sanfilippo"
__credits__ = ["Max Smith", "Salvatore Sanfilippo"]
__license__ = """
BSD License
Copyright (c) 2006-2009, Salvatore Sanfilippo
Copyright (c) 2014, Max Smith
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
following conditions are met:

    * Redistributions of source code must retain the above copyright notice, this list of conditions and the
      following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the
      following disclaimer in the documentation and/or other materials provided with the distribution.
    * Neither the name of Smaz nor the names of its contributors may be used to endorse or promote products
      derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
__version__ = "1.0.1"
__maintainer__ = "Max Smith"
__email__ = None

try:
    # noinspection PyShadowingBuiltins
    xrange = range  # Fix for python 3 compatibility.
except NameError:
    pass

BACKTRACK_LIMIT = 254  # No point backtracking more than 255 characters


def make_trie(decode_table):
    """ Create a trie representing the encoding strategy implied by the passed table.
        For each string in the table, assign it an encoded value, walk through the string
        creating a node for each character at a position (if none already exists), and when
        we reach the end of the string populate that node with the assigned encoded value.

    :param decode_table: list
    """
    empty_node = list(None for _ in xrange(0, 256))
    root_node = list(empty_node)
    if not decode_table:
        raise ValueError('Empty data passed to make_tree')
    elif len(decode_table) > 254:
        raise ValueError('Too long list in make tree: %d' % len(decode_table))
    else:
        for enc_byte, sstr in enumerate(decode_table):
            node_ptr = root_node
            for str_pos, ch in enumerate(sstr):
                ord_ch = ord(ch)
                if node_ptr[ord(ch)]:  # If a child node exists for character
                    terminal_byte, children = node_ptr[ord_ch]
                    if len(sstr) == str_pos + 1:  # At the end ?
                        if not terminal_byte:
                            node_ptr[ord_ch] = [chr(enc_byte), children]
                            break
                        else:
                            raise ValueError('Unexpected terminal: duplicates in data (%s) (%s) (%s)' %
                                             (sstr, ch, node_ptr))
                    node_ptr = children
                else:  # Create the child node
                    if len(sstr) == str_pos + 1:  # At the end ?
                        node_ptr[ord_ch] = [chr(enc_byte), list(empty_node)]
                    else:
                        node_ptr[ord_ch] = [None, list(empty_node)]
                        _, node_ptr = node_ptr[ord_ch]
    # Now we've built the trie, we can optimize it a bit by replacing empty terminal nodes early with None
    stack = list(root_node)
    while stack:
        node_ptr = stack.pop()
        if node_ptr:
            _, children = node_ptr
            if children == empty_node:
                node_ptr[1] = None  # Replace empty entries with None
            else:
                stack.extend(children)
    return root_node


def make_tree(decode_table):
    """ Create a tree representing the encoding strategy implied by the passed table.
        For each string in the table, assign it an encoded value, walk through the string
        creating a node for each character at a position (if none already exists), and when
        we reach the end of the string populate that node with the assigned encoded value.

    :param decode_table: list
    """
    root_node = {}
    if not decode_table:
        raise ValueError('Empty data passed to make_tree')
    elif len(decode_table) > 254:
        raise ValueError('Too long list in make tree: %d' % len(decode_table))
    else:
        for enc_byte, sstr in enumerate(decode_table):
            node_ptr = root_node
            for str_pos, ch in enumerate(sstr):
                if node_ptr.get(ch):  # If a child node exists for character
                    terminal_byte, children = node_ptr.get(ch)
                    if len(sstr) == str_pos + 1:  # At the end ?
                        if not terminal_byte:
                            node_ptr[ch] = (chr(enc_byte), children)
                            break
                        else:
                            raise ValueError('Unexpected terminal: duplicates in data (%s) (%s) (%s)' %
                                             (sstr, ch, node_ptr))
                    node_ptr = children
                else:  # Create the child node
                    if len(sstr) == str_pos + 1:  # At the end ?
                        node_ptr[ch] = (chr(enc_byte), {})
                    else:
                        node_ptr[ch] = (None, {})
                        _, node_ptr = node_ptr[ch]
    return root_node


# Can be up to 253 entries in this table.
DECODE = ["+", "the", "e", "t", "a", "of", "o", "and", "i", "n", "s", "e ", "r", " th",
          "+t", "in", "he", "th", "h", "he ", "to", "https://", "l", "s ", "d", " a", "an",
          "er", "c", " o", "d ", "on", " of", "re", "of ", "t ", "www.", "is", "u", "at",
          "xn--", "n ", "or", "which", "f", "m", "as", "it", "that", "%", "was", "en",
          "about", " w", "es", " an", " i", "\r", "f ", "g", "p", "nd", " s", "nd ", "ed ",
          "w", "ed", "http://", "for", "te", "ing", "y ", "The", " c", "ti", "r ", "his",
          "st", " in", "ar", "nt", ",", " to", "y", "ng", " h", "with", "le", "al", "to ",
          "b", "ou", "be", "were", " b", "se", "o ", "ent", "ha", "ng ", "their", "_",
          "hi", "from", " f", "in ", "de", "ion", "me", "v", ".", "ve", "all", "re ",
          "ri", "ro", "is ", "co", "f t", "are", "ea", ". ", "her", " m", "er ", " p",
          "es ", "by", "they", "di", "ra", "ic", "not", "s, ", "d t", "at ", "ce", "la",
          "h ", "ne", "as ", "tio", "on ", "n t", "io", "we", " a ", "om", ", a", "s o",
          "ur", "li", "ll", "ch", "had", "this", "e t", "g ", ".ru", " wh", "ere",
          " co", "e o", "a ", "us", " d", "ss", ".org", ".html", "vk.com", " be", " e",
          "s a", "ma", "one", "t t", "or ", "but", "el", "so", "l ", "e s", "s,", "no",
          "ter", " wa", "iv", "ho", "e a", " r", "hat", "s t", "ns", "ch ", "wh", "tr",
          "ut", "/", "have", "ly ", "ta", " ha", " on", "tha", "-", " l", "ati", "en ",
          "pe", " re", "there", "ass", "si", " fo", "wa", "ec", "our", "who", "its", "z",
          "fo", "rs", "#", "ot", "un", "&", "im", "th ", "nc", "ate", "info", "ver", "ad",
          " we", "ly", "ee", " n", "id", " cl", "ac", "il", "www", "rt", " wi", "div",
          "e, ", " it", "whi", " ma", "ge", "x", "e c", "men", ".com"]

# Can be regenerated with the below line
SMAZ_TREE = make_trie(DECODE)


def _check_ascii(sstr):
    """ Return True iff the passed string contains only ascii chars """
    return all(ord(ch) < 128 for ch in sstr)


def _encapsulate(input_str):
    """ There are some pathological cases, where it may be better to just encapsulate the string in 255 code chunks
    """
    if not input_str:
        return input_str
    else:
        output = []
        output_append = output.append
        for chunk in (input_str[i:i+255] for i in xrange(0, len(input_str), 255)):
            if 1 == len(chunk):
                output_append(chr(254) + chunk)
            else:
                output_append(chr(255) + chr(len(chunk) - 1))
                output_append(chunk)
        return "".join(output)


def _encapsulate_list(input_list):
    """ There are some pathological cases, where it may be better to just encapsulate the string in 255 code chunks
    """
    if not input_list:
        return input_list
    else:
        output = []
        output_append = output.append
        output_extend = output.extend
        for chunk in (input_list[i:i+255] for i in xrange(0, len(input_list), 255)):
            if 1 == len(chunk):
                output_append(chr(254))
                output_extend(chunk)
            else:
                output_extend((chr(255), chr(len(chunk) - 1)))
                output_extend(chunk)
        return output


def _worst_size(str_len):
    """ Given a string length, what's the worst size that we should grow to """
    if str_len == 0:
        return 0
    elif str_len == 1:
        return 2
    elif str_len % 255 in (0, 1):
        return (str_len / 255) * 2 + str_len + (str_len % 255)
    else:
        return ((str_len / 255) + 1) * 2 + str_len


def compress_no_backtracking(input_str):
    """ As ccmpress, but with backtracking and pathological case detection, and ascii checking disabled """
    return compress(input_str, check_ascii=False, backtracking=False, pathological_case_detection=False)


def compress(input_str, check_ascii=True, raise_on_error=True, compression_tree=None, backtracking=True,
             pathological_case_detection=True, backtrack_limit=BACKTRACK_LIMIT):
    """ Compress the passed string using the SMAZ algorithm. Returns the encoded string. Performance is a O(N), but the
        constant will vary depending on the relationship between the compression tree and input_str, in particular the
        average depth explored/average characters per encoded symbol.


    :param input_str The ASCII str to be compressed
    :param check_ascii Check the input_str is ASCII before we encode it (default True)
    :param raise_on_error Throw a value type exception (default True)
    :param compression_tree: A tree represented as a dict of ascii char to tuple( encoded_byte, dict( ... ) ), that
                             describes how to compress content. By default uses built in SMAZ tree. See also make_tree
    :param backtracking: Enable checking for poor performance of the standard algorithm, some performance impact
                             True = better compression (1% on average), False = Higher throughput
    :param pathological_case_detection: A lighter version of backtracking to catch output growth beyond the
                             simple worst case handling of encapsulation. You probably want this enabled.
    :param backtrack_limit: How many characters to look backwards for backtracking, defaults to 255 - setting it higher
                            may achieve slightly higher compression ratios (0.1% on big strings) at the expense of much
                            worse performance, particularly on random data. You probably want this left as default

    :type input_str: str
    :type check_ascii: bool
    :type raise_on_error: bool
    :type compression_tree: dict
    :type backtracking: bool
    :type pathological_case_detection: bool

    :rtype: str
    :return: The compressed input_str
    """
    if not input_str:
        return input_str
    else:
        if check_ascii and not _check_ascii(input_str):
            if raise_on_error:
                raise ValueError('SMAZ can only process ASCII text.')
            else:
                return None

        # Invariants:
        terminal_tree_node = (None, None)
        compression_tree = compression_tree or SMAZ_TREE
        input_str_len = len(input_str)

        # Invariant: All of these arrays assume len(array) = number of bytes in array
        output = []          # Single bytes. Committed, non-back-track-able output
        unmatched = []       # Single bytes. Current pool for encapsulating (i.e. 255/254 + unmatched)
        backtrack_buff = []  # Single bytes. Encoded between last_backtrack_pos and pos (excl enc_buf and unmatched)
        enc_buf = []         # Single bytes. Encoded output for the current run of compression codes

        # Ugly but fast
        output_extend = output.extend

        last_backtrack_pos = pos = 0
        while pos < input_str_len:
            tree_ptr = compression_tree
            enc_byte = None
            j = 0
            while j < input_str_len - pos:  # Search the tree for the longest matching sequence
                byte_val, tree_ptr = tree_ptr[ord(input_str[pos + j])] or terminal_tree_node
                j += 1
                if byte_val is not None:
                    enc_byte = byte_val  # Remember this match, and search for a longer one
                    enc_len = j
                if not tree_ptr:
                    break  # No more matching characters in the tree

            if enc_byte is None:
                unmatched.append(input_str[pos])
                pos += 1  # We didn't match any stems, add the character the unmatched list

                # Backtracking - sometimes it makes sense to go back and not use a length one symbol between two runs of
                # raw text, since the cost of the context switch is 2 bytes. The following code looks backwards and
                # tries to judge if the mode switches left us better or worse off. If worse off, re-encode the text as
                # a raw text run.
                if len(enc_buf) > 0 or input_str_len == pos:
                    # Mode switch ! or end of string
                    merge_len = _worst_size(pos - last_backtrack_pos)
                    unmerge_len = len(backtrack_buff) + len(enc_buf) + _worst_size(len(unmatched))
                    if merge_len > unmerge_len + 2 or pos - last_backtrack_pos > backtrack_limit or not backtracking:
                        # Unmerge: gained at least 3 bytes through encoding, reset the backtrack marker to here
                        output_extend(backtrack_buff)
                        output_extend(enc_buf)
                        backtrack_buff = []
                        last_backtrack_pos = pos - 1
                    elif merge_len < unmerge_len:
                        # Merge: Mode switch doesn't make sense, don't move backtrack marker
                        backtrack_buff = []
                        unmatched = list(input_str[last_backtrack_pos:pos])
                    else:
                        # Gains are two bytes or less - don't move the backtrack marker till we have a clear gain
                        backtrack_buff.extend(enc_buf)
                        if input_str_len == pos:
                            backtrack_buff.extend(_encapsulate_list(unmatched))
                            unmatched = []
                    enc_buf = []
            else:
                # noinspection PyUnboundLocalVariable
                pos += enc_len  # We did match in the tree, advance along, by the number of bytes matched
                enc_buf.append(enc_byte)
                if unmatched:  # Entering an encoding run
                    backtrack_buff.extend(_encapsulate_list(unmatched))
                    unmatched = []

        output_extend(backtrack_buff)
        output_extend(_encapsulate_list(unmatched))
        output_extend(enc_buf)

        # This may look a bit clunky, but it is worth 20% in cPython and O(n^2) -> O(n) in PyPy
        output = "".join(output)

        # Pathological case detection - Did we grow more than we would by encapsulating the string ?
        # There are some cases where backtracking doesn't work correctly, examples:
        # Y OF
        if pathological_case_detection:
            worst = _worst_size(input_str_len)
            if len(output) > worst:
                return _encapsulate(input_str)
        return output


def compress_classic(input_str, pathological_case_detection=True):
    """ A trie version of the original SMAZ compressor, should give identical output to C version.
        Faster on typical material, but can be tripped up by pathological cases.
        :type input_str: str
        :type pathological_case_detection: bool

        :param input_str The string to be compressed
        :param pathological_case_detection Look for growth beyond the worst case of encapsulation and encapsulate
               default is True, you probably want this enabled.

        :rtype: str
        :return: The compressed input_str
        """
    if not input_str:
        return input_str
    else:
        # Invariants:
        terminal_tree_node = (None, None)
        input_str_len = len(input_str)

        # Invariant: All of these arrays assume len(array) = number of bytes in array
        output = []     # Single bytes. Committed, non-back-track-able output
        unmatched = []  # Single bytes. Current pool for encapsulating (i.e. 255/254 + unmatched)

        # So this is ugly - but fast
        output_extend = output.extend
        output_append = output.append

        pos = 0
        while pos < input_str_len:
            tree_ptr = SMAZ_TREE
            enc_byte = None
            j = 0
            while j < input_str_len - pos:  # Search the tree for the longest matching sequence
                byte_val, tree_ptr = tree_ptr[ord(input_str[pos + j])] or terminal_tree_node
                j += 1
                if byte_val is not None:
                    enc_byte = byte_val  # Remember this match, and search for a longer one
                    enc_len = j
                if not tree_ptr:
                    break  # No more matching characters in the tree

            if enc_byte is None:
                unmatched.append(input_str[pos])
                pos += 1  # We didn't match any stems, add the character the unmatched list
            else:
                # noinspection PyUnboundLocalVariable
                pos += enc_len  # We did match in the tree, advance along, by the number of bytes matched
                if unmatched:  # Entering an encoding run
                    output_extend(_encapsulate_list(unmatched))
                    unmatched = []
                output_append(enc_byte)
        if unmatched:
            output_extend(_encapsulate_list(unmatched))

        if pathological_case_detection and len(output) > _worst_size(input_str_len):
            return _encapsulate(input_str)
        else:
            return "".join(output)


def decompress(input_str, raise_on_error=True, check_ascii=False, decompress_table=None):
    """ Returns decoded text from the input_str using the SMAZ algorithm by default
        :type input_str: str
        :type raise_on_error: bool
        :type check_ascii: bool
        :type decompress_table: list

        :param raise_on_error Throw an exception on any kind of decode error, if false, return None on error
        :param check_ascii Check that all output is ASCII. Will raise or return None depending on raise_on_error
        :param decompress_table Alternative 253 entry decode table, by default uses SMAZ

        :rtype: str
        :return: The decompressed input_str
    """
    if not input_str:
        return input_str
    else:
        decompress_table = decompress_table or DECODE
        input_str_len = len(input_str)
        output = []
        output_append = output.append
        pos = 0
        try:
            while pos < input_str_len:
                ch = ord(input_str[pos])
                pos += 1
                if ch < 254:
                    # Code table entry
                    output_append(decompress_table[ch])
                else:
                    next_byte = input_str[pos]
                    pos += 1
                    if 254 == ch:
                        # Verbatim byte
                        output_append(next_byte)
                    else:  # 255 == ch:
                        # Verbatim string
                        end_pos = pos + ord(next_byte) + 1
                        if end_pos > input_str_len:
                            raise ValueError('Invalid input to decompress - buffer overflow')
                        output_append(input_str[pos:end_pos])
                        pos = end_pos
            # This may look a bit clunky, but it is worth 20% in cPython and O(n^2)->O(n) in PyPy
            output = "".join(output)
            if check_ascii and not _check_ascii(output):
                raise ValueError('Invalid input to decompress - non-ascii byte payload')
        except (IndexError, ValueError) as e:
            if raise_on_error:
                raise ValueError(str(e))
            else:
                return None
        return output
