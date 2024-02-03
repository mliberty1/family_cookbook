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
import shutil
import json


_MYPATH = os.path.dirname(__file__)
_BUILD = os.path.join(_MYPATH, 'build')
_HTML = os.path.join(_BUILD, 'html')


def _generate():
    with open(os.path.join(_MYPATH, 'cookbook.jsonld'), 'rt', encoding='utf-8') as src:
        data = json.load(src)
    shutil.rmtree(_HTML, ignore_errors=True)
    os.makedirs(_HTML, exist_ok=True)
    for recipe in data:
        print(recipe['name'])


if __name__ == '__main__':
    _generate()
