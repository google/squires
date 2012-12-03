#!/usr/bin/python
#
# Copyright 2010 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.

import os
import unittest

import option_lib

TEST_PATH = '.'


class CommandsTest(unittest.TestCase):

  def testOption(self):
    """Test the Option() class."""
    option = option_lib.Option(name='foo', helptext='bar')
    # Make sure Match picks up variants of the name
    # throughout the command line.
    self.failUnlessEqual(1, option.FindMatches(['foo'], 0).count)
    self.failUnlessEqual(1, option.FindMatches(['foo', 'bar'], 0).count)
    self.failUnlessEqual(1, option.FindMatches(['bar', 'foo'], 1).count)
    self.failUnlessEqual(1, option.FindMatches(['fo'], 0).count)
    self.failUnlessEqual(1, option.FindMatches(['f'], 0).count)
    self.failUnlessEqual(1, option.FindMatches(['f', 'bar'], 0).count)
    self.failUnlessEqual(1, option.FindMatches(['bar', 'f'], 1).count)
    self.failUnlessEqual(0, option.FindMatches(['baz'], 0).count)
    self.failUnlessEqual(0, option.FindMatches(['baz', 'bar'], 0).count)

    # Do the same for regex match based non-boolean options.
    option = option_lib.Option(name='<aid>', boolean=False,
                               match='\d[a-z]\d', helptext='bar')
    self.failUnlessEqual(option.FindMatches(['2e2'], 0).value, '2e2')
    self.failUnlessEqual(option.FindMatches(['foobar', '2e2'], 1).value, '2e2')
    self.failUnlessEqual(option.FindMatches(['2e2', 'foobar'], 0).value, '2e2')
    self.failUnlessEqual(option.FindMatches(['e2e'], 0).value, None)
    self.failUnlessEqual(option.FindMatches(['e2e', 'foo'], 0).value, None)

    # And boolean regex based options.
    option = option_lib.Option(name='<aid>', boolean=True,
                               match='\d[a-z]\d', helptext='bar')
    self.failUnlessEqual(option.FindMatches(['2e2'], 0).value, True)
    self.failUnlessEqual(option.FindMatches(['foobar', '2e2'], 1).value, True)
    self.failUnlessEqual(option.FindMatches(['2e2', 'foobar'], 0).value, True)
    self.failUnlessEqual(option.FindMatches(['e2e'], 0).value, False)
    self.failUnlessEqual(option.FindMatches(['e2e', 'foo'], 0).value, False)

    # List based options
    option = option_lib.Option(name='alist', boolean=False,
                               match=['one', 'two', 'three', 'four'],
                               helptext='Some help')
    line = ['t', '']
    self.failUnlessEqual({'two': '', 'three': ''},
                         option.FindMatches(line, 0).valid)
    self.failUnlessEqual({'one': '', 'two': '', 'three': '', 'four': ''},
                         option.FindMatches(line, 1).valid)
    line = ['bar', ' ']
    self.failUnlessEqual({'one': '', 'two': '', 'three': '', 'four': ''},
                         option.FindMatches(line, 1).valid)
    self.failUnlessEqual({},
                         option.FindMatches(line, 0).valid)


class MatchTest(unittest.TestCase):
  """Test options_lib.BaseMatch classes."""

  def testBoolean(self):
    bm = option_lib.BooleanMatch('green', 'Make it green')
    self.assertTrue(bm.Matches(['green'], 0))
    self.assertFalse(bm.Matches(['blue'], 0))

    self.assertTrue(bm.GetMatch(['green'], 0))
    self.assertFalse(bm.GetMatch(['blue'], 0))

    self.assertEqual({'green': 'Make it green'},
                     bm.GetValidMatches(['green'], 0))
    self.assertEqual({'green': 'Make it green'},
                     bm.GetValidMatches(['gr'], 0))
    self.assertEqual({}, bm.GetValidMatches(['blue'], 0))

  def testRegex(self):
    opt = option_lib.Option(name='<interface>')
    bm = option_lib.RegexMatch('[fgx]e-.*', 'A Juniper ethernet interface', opt)
    self.assertTrue(bm.Matches(['ge-0/0/0'], 0))
    self.assertFalse(bm.Matches(['so-1/0/0'], 0))

    self.assertEqual('ge-0/0/0', bm.GetMatch(['ge-0/0/0'], 0))
    self.assertEqual(None, bm.GetMatch(['so-0/0/0'], 0))

    self.assertEqual({'ge-0/0/0': 'A Juniper ethernet interface'},
                     bm.GetValidMatches(['ge-0/0/0'], 0))
    self.assertEqual({'<<interface>>':
                      'A Juniper ethernet interface ([fgx]e-.*)'},
                     bm.GetValidMatches([''], None))
    self.assertEqual({},
                     bm.GetValidMatches(['so-0/0/0'], 0))

  def testMultiword(self):
    opt = option_lib.Option(name='<interface>', multiword=True)
    bm = option_lib.RegexMatch('\d+[^\d]+\d+', 'A Juniper ethernet interface', opt)
    self.assertEqual(0, bm.Matches(['one', 'two', '344'], 0))
    self.assertEqual(2, bm.Matches(['one', '34 two', '34 and 35', 'blahfrub'], 1))
    self.assertEqual(2, bm.Matches(['zero', 'one', '34 two', '34 and 35', 'blahfrub'], 2))

  def testList(self):
    bm = option_lib.ListMatch(
        ['red', 'black', 'blue', 'blueish', 'green'], 'A colour',
        option_lib.Option('foo'))
    self.assertTrue(bm.Matches(['red'], 0))
    self.assertTrue(bm.Matches(['blue'], 0))
    self.assertFalse(bm.Matches(['white'], 0))

    self.assertEqual('blue', bm.GetMatch(['blue'], 0))
    self.assertEqual('blueish', bm.GetMatch(['blueish'], 0))
    self.assertEqual(None, bm.GetMatch(['wh'], 0))

    self.assertEqual({'blue': '', 'black': '',
                      'blueish': ''},
                     bm.GetValidMatches(['bl'], 0))
    self.assertEqual({'red': '',
                      'black': '',
                      'blue': '',
                      'blueish': '',
                      'green': ''},
                     bm.GetValidMatches([''], 0))
    self.assertEqual({},
                     bm.GetValidMatches(['wh'], 0))

  def testListRegexMatch(self):
    bm = option_lib.ListMatch(['/wi*/', '/bo*/', 'foobar'], 'foo',
                              option_lib.Option(['foo'], 0))
    self.assertTrue(bm.Matches(['w'], 0))
    self.assertTrue(bm.Matches(['wi'], 0))
    self.assertTrue(bm.Matches(['wiiiiiiiiiiii'], 0))
    self.assertTrue(bm.Matches(['b'], 0))
    self.assertTrue(bm.Matches(['bo'], 0))
    self.assertTrue(bm.Matches(['booooooooooooooo'], 0))
    self.assertTrue(bm.Matches(['foobar'], 0))
    self.assertFalse(bm.Matches(['zzzzzzz'], 0))

    self.assertEqual('foobar', bm.GetMatch(['fo'], 0))
    self.assertEqual(None, bm.GetMatch(['wiii'], 0))

    self.assertEqual({'foobar': '', '/bo*/': '', '/wi*/': ''},
                     bm.GetValidMatches([''], 0))
    self.assertEqual({}, bm.GetValidMatches(['booo'], 0))

  def testDict(self):
    bm = option_lib.DictMatch(
        {'red': 'The colour red',
         'black': 'The colour black',
         'blue': 'The colour blue',
         'blueish': 'A sort of blue',
         'green': 'The colour green'}, option_lib.Option('foo'))
    self.assertTrue(bm.Matches(['red'], 0))
    self.assertTrue(bm.Matches(['blue'], 0))
    self.assertTrue(bm.Matches(['blueish'], 0))
    self.assertFalse(bm.Matches(['white'], 0))

    self.assertEqual('blue', bm.GetMatch(['blue'], 0))
    self.assertEqual('blueish', bm.GetMatch(['blueish'], 0))
    self.assertEqual(None, bm.GetMatch(['wh'], 0))

    self.assertEqual({'blue': 'The colour blue',
                      'black': 'The colour black',
                      'blueish': 'A sort of blue'},
                     bm.GetValidMatches(['bl'], 0))
    self.assertEqual({'red': 'The colour red',
                      'black': 'The colour black',
                      'blue': 'The colour blue',
                      'blueish': 'A sort of blue',
                      'green': 'The colour green'},
                     bm.GetValidMatches([''], 0))
    self.assertEqual({},
                     bm.GetValidMatches(['wh'], 0))

  def testDictRegexMatch(self):
    bm = option_lib.DictMatch(
        {'foobar': 'foobar',
         '/wi*/': 'hurray',
         '/bo*/': 'booooo'}, option_lib.Option('foo'))

    self.assertTrue(bm.Matches(['foobar'], 0))
    self.assertTrue(bm.Matches(['w'], 0))
    self.assertTrue(bm.Matches(['wi'], 0))
    self.assertTrue(bm.Matches(['wiiii'], 0))
    self.assertTrue(bm.Matches(['b'], 0))
    self.assertTrue(bm.Matches(['boooooo'], 0))
    self.assertFalse(bm.Matches(['zzzzzzz'], 0))

    self.assertEqual({'foobar': 'foobar',
                      '/wi*/': 'hurray',
                      '/bo*/': 'booooo'},
                     bm.GetValidMatches([''], 0))
    self.assertEqual({},
                     bm.GetValidMatches(['zzz'], 0))
    self.assertEqual({'foobar': 'foobar'},
                     bm.GetValidMatches(['fo'], 0))

  def testMethod(self):
    def MatchMethod(option):
      return {
          'red': 'The colour red',
          'black': 'The colour black',
          'blue': 'The colour blue',
          'blueish': 'A sort of blue',
          'green': 'The colour green'}

    bm = option_lib.MethodMatch(MatchMethod, option_lib.Option('foo'))
    self.assertTrue(bm.Matches(['red'], 0))
    self.assertTrue(bm.Matches(['blue'], 0))
    self.assertTrue(bm.Matches(['blueish'], 0))
    self.assertFalse(bm.Matches(['white'], 0))

    self.assertEqual('blue', bm.GetMatch(['blue'], 0))
    self.assertEqual('blueish', bm.GetMatch(['blueish'], 0))
    self.assertEqual(None, bm.GetMatch(['wh'], 0))

    self.assertEqual({'blue': 'The colour blue',
                      'black': 'The colour black',
                      'blueish': 'A sort of blue'},
                     bm.GetValidMatches(['bl'], 0))
    self.assertEqual({'red': 'The colour red',
                      'black': 'The colour black',
                      'blue': 'The colour blue',
                      'blueish': 'A sort of blue',
                      'green': 'The colour green'},
                     bm.GetValidMatches([''], 0))
    self.assertEqual({},
                     bm.GetValidMatches(['wh'], 0))

  def testPath(self):
    """Tests path matching."""
    fm = option_lib.PathMatch(None, None)
    self.assertTrue(fm.Matches(['blah'], 0))
    self.assertTrue(fm.Matches(['/etc'], 0))
    self.assertFalse(fm.Matches([''], 0))
    self.assertFalse(fm.Matches([' '], 0))

    fm = option_lib.PathMatch(None, option_lib.Option('foo'),
                              only_existing=True,
                              default_path='./testdata/')
    matches = fm.GetValidMatches([''], 0)
    if '.svn/' in matches:
      del matches['.svn/']
    self.assertEqual({'boo1': '', 'boo2': '', 'file1': ''}, matches)

    self.assertEqual(
        {'file1': ''},
        fm.GetValidMatches(['f'], 0))

    self.assertEqual(
        {'boo1': '', 'boo2': ''},
        fm.GetValidMatches(['bo'], 0))

    self.assertTrue(fm.Matches(['boo1'], 0))
    self.assertFalse(fm.Matches(['boo'], 0))
    self.assertFalse(fm.Matches(['blum'], 0))

    self.assertEqual(None, fm.GetMatch(['boo'], 0))
    self.assertEqual('boo1', fm.GetMatch(['boo1'], 0))

    fm = option_lib.PathMatch(None, option_lib.Option('foo'),
                              only_existing=True,
                              only_dirs=True)

    matches = fm.GetValidMatches([''], 0)
    if '.svn/' in matches:
      del matches['.svn/']
    self.assertEqual({'testdata/': ''}, matches)


if __name__ == '__main__':
  unittest.main()
