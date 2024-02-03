# Copyright 2023 Matthew Liberty
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json


_MYPATH = os.path.dirname(__file__)


def _get_field(lines, field):
    line_num, line = next(lines)
    sline = line.strip()
    parts = sline.split(' = ')
    if len(parts) == 1:
        return ''
    elif len(parts) == 2:
        value = parts[1]
    else:
        raise ValueError(f'ERROR on line {line_num + 1}: {sline}')
    if field != parts[0]:
        raise RuntimeError(f'ERROR on line {line_num + 1}: {line} "{field}" != "{parts[0]}"')
    return value


def _txt_convert():
    data = []
    src = open(os.path.join(_MYPATH, 'cookbook.txt'), 'rt', encoding='utf-8')
    lines = enumerate(src.readlines())
    while lines:
        try:
            line_num, line = next(lines)
        except StopIteration:
            break
        sline = line.strip()
        if not sline:
            continue
        if sline != '@':
            continue
        r = {
            "@context": "https://schema.org",
            "@type": "Recipe",
            'creativeWorkStatus': 'Published',
            'dateCreated': "1997-12-21",
            'dateModified': '2024-01-01',
            "datePublished": "1997-12-21",
        }
        data.append(r)
        r['name'] = _get_field(lines, 'NAME')
        r['recipeCategory'] = _get_field(lines, 'CATEGORY')
        r['author'] = _get_field(lines, 'USER_ID')
        r['description'] = _get_field(lines, 'DESCRIPTION')
        r['educationalLevel'] = _get_field(lines, 'DIFFICULTY')
        _get_field(lines, 'FILENAME')
        prep = _get_field(lines, 'PREP')
        r['totalTime'] = f'PT{prep}M'
        serves = _get_field(lines, 'SERVES')
        _get_field(lines, 'TIMESTAMP')
        if len(serves):
            if ' ' not in serves:
                serves = f'{serves} servings'
            r['recipeYield'] = serves
        else:
            r['recipeYield'] = 'TODO'
        r['recipeIngredient'] = []
        r['recipeInstructions'] = []
        section = None
        while True:
            line_num, line = next(lines)
            sline = line.strip()
            if not len(sline):
                break
            if line[0] == '[':
                if sline == '[Ingredients.00000000]':
                    section = r['recipeIngredient']
                elif sline.startswith('[Ingredients.'):
                    ingredient_group = sline.split('.')[-1][:-1]
                    section = r['recipeIngredient']
                    section.append(f'## {ingredient_group}')  # nonstandard
                elif sline == '[Instructions.00000000]':
                    section = r['recipeInstructions']
                elif sline == '[Comments.00000000]':
                    section = None
                    line_num, line = next(lines)
                    r['recipeInstructions'].append(f'🛈 {line.strip()}')  # nonstandard
                    next(lines)
                    next(lines)
                    next(lines)
                else:
                    raise RuntimeError('unknown section')
            else:
                section.append(sline)

    with open(os.path.join(_MYPATH, 'cookbook.jsonld'), 'wt', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    _txt_convert()
