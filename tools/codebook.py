#!/usr/bin/env python3

import re
from operator import itemgetter
from collections import defaultdict

from smaz import compress, decompress, make_trie


def get_next_best_substring(strings):
    max_ngram_size = 200
    substrings = defaultdict(int)

    alpha_tokens = re.compile(r'[a-z0-9]{' + str(max_ngram_size + 1) + r',}', re.IGNORECASE)
    alpha_slash_dot_tokens = re.compile(r'[a-z0-9.-/]{' + str(max_ngram_size + 1) + r',}', re.IGNORECASE)
    for string, count in strings.items():
        length = len(string)
        if length == 0:
            continue

        for x in re.findall(alpha_tokens, string):
            substrings[x] += count
        for x in filter(lambda t: '/' in t, re.findall(alpha_slash_dot_tokens, string)):
            substrings[x] += count

        # Generate n-grams
        for j in range(length):
            remaining_chars = length - j
            k = 2
            while k <= max_ngram_size and k <= remaining_chars:
                substrings[string[j:j + k]] += count
                k += 1

    # Get best substring based on length and number of occurrences
    best_score = 0
    best_substring = ''
    for substring, count in substrings.items():
        score = count * pow(len(substring), 2.2)
        if score > best_score:
            best_substring = substring
            best_score = score

    return best_substring


def get_compression_ratio(codebook, strings):
    total_compressed = 0
    total_uncompressed = 0
    compression_tree = make_trie(codebook)

    for string, count in strings.items():
        compressed = compress(string, compression_tree=compression_tree)
        total_compressed += len(compressed) * count
        total_uncompressed += len(string) * count

    return 100.0 * total_compressed / total_uncompressed


def generate(original_strings):
    strings = original_strings
    codebook = []

    for i in range(254):
        substring = get_next_best_substring(strings)
        if not substring:
            print('No more strings {}'.format(i))
            break

        print('>>>> {} {}'.format(i, substring))

        codebook.append(substring)

        new_strings = defaultdict(int)
        for string, count in strings.items():
            if string.find(substring) != -1:
                for s in string.split(substring):
                    new_strings[s] += count
            else:
                new_strings[string] += count

        strings = new_strings

    # Count remaining occurrences of letters in strings
    letters = defaultdict(int)
    for string in original_strings:
        for c in string:
            letters[c] += 1

    best_ratio = get_compression_ratio(codebook, original_strings)

    # Fine-tune codebook with letters sorted from most popular to least popular
    for letter, popularity in sorted(letters.items(), key=itemgetter(1), reverse=True):
        # If codebook is not full yet, just add the letter at the end
        if len(codebook) < 254:
            codebook.append(letter)
            print('Codebook not full, adding letter: {}'.format(letter))
            continue

        # Codebook is full, try to find a spot
        best_r = 100
        insert_at = -1
        print('> letter', letter)
        for i in range(len(codebook)):
            prev = codebook[i]
            codebook[i] = letter
            ratio = get_compression_ratio(codebook, original_strings)
            codebook[i] = prev
            if ratio < best_r:
                best_r = ratio
                insert_at = i

        if best_r < best_ratio:
            print('replacing {} with {} = {}%'.format(codebook[insert_at], letter, best_r))
            codebook[insert_at] = letter
            best_ratio = best_r

    return codebook


spaces_pattern = re.compile(r'\s{2,}')
comas_pattern = re.compile(r'\s,')
dotcomas_pattern = re.compile(r'\s;')

if __name__ == "__main__":
    strings = defaultdict(int)
    with open('phones.txt') as in_file:
        for line in in_file:
            if not line.isascii():
                continue
            line = line.replace('"', '').strip()
            line = spaces_pattern.sub(' ', line)
            line = comas_pattern.sub(',', line)
            line = dotcomas_pattern.sub(';', line)
            strings[line] += 1

    codebook = generate(strings)

    print('DECODE = [')
    for item in codebook:
        print('    "{}",'.format(item))
    print(']')
    print('')
    print('')

    test_str = 'Mo-Fr 08:30-15:30; Jan 01,Apr 19,May 01,Jun 24,Jul 05,Jul 24,Oct 12,Dec 24,Dec 25,Dec 31 off'
    compressed = compress(test_str, compression_tree=make_trie(codebook))
    print(compressed)
    print(decompress(compressed, decompress_table=codebook))
