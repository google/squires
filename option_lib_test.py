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
    self.failUnless(option.Match(['foo'], None))
    self.failUnless(option.Match(['foo', 'bar'], None))
    self.failUnless(option.Match(['bar', 'foo'], None))
    self.failUnless(option.Match(['fo'], None))
    self.failUnless(option.Match(['f'], None))
    self.failUnless(option.Match(['f', 'bar'], None))
    self.failUnless(option.Match(['bar', 'f'], None))
    self.failIf(option.Match(['baz'], None))
    self.failIf(option.Match(['baz', 'bar'], None))

    # Do the same for regex match based non-boolean options.
    option = option_lib.Option(name='<aid>', boolean=False,
                               match='\d[a-z]\d', helptext='bar')
    self.failUnlessEqual(option.Match(['2e2'], None), '2e2')
    self.failUnlessEqual(option.Match(['foobar', '2e2'], None), '2e2')
    self.failUnlessEqual(option.Match(['2e2', 'foobar'], None), '2e2')
    self.failUnlessEqual(option.Match(['e2e'], None), None)
    self.failUnlessEqual(option.Match(['e2e', 'foo'], None), None)

    # And boolean regex based options.
    option = option_lib.Option(name='<aid>', boolean=True,
                               match='\d[a-z]\d', helptext='bar')
    self.failUnlessEqual(option.Match(['2e2'], None), True)
    self.failUnlessEqual(option.Match(['foobar', '2e2'], None), True)
    self.failUnlessEqual(option.Match(['2e2', 'foobar'], None), True)
    self.failUnlessEqual(option.Match(['e2e'], None), None)
    self.failUnlessEqual(option.Match(['e2e', 'foo'], None), None)

    # List based options
    option = option_lib.Option(name='alist', boolean=False,
                               match=['one', 'two', 'three', 'four'],
                               helptext='Some help')
    self.failUnlessEqual({'two': '', 'three': ''},
                         option.GetMatches('t'))
    self.failUnlessEqual({'one': '', 'two': '', 'three': '', 'four': ''},
                         option.GetMatches(''))
    self.failUnlessEqual({'one': '', 'two': '', 'three': '', 'four': ''},
                         option.GetMatches(' '))
    self.failUnlessEqual({},
                         option.GetMatches('bar'))


class MatchTest(unittest.TestCase):
  """Test options_lib.BaseMatch classes."""

  def testBoolean(self):
    bm = option_lib.BooleanMatch('green', 'Make it green')
    self.assertTrue(bm.Matches('green'))
    self.assertFalse(bm.Matches('blue'))

    self.assertTrue(bm.GetMatch('green'))
    self.assertFalse(bm.GetMatch('blue'))

    self.assertEqual({'green': 'Make it green'},
                     bm.GetValidMatches('green'))
    self.assertEqual({'green': 'Make it green'},
                     bm.GetValidMatches('gr'))
    self.assertEqual({}, bm.GetValidMatches('blue'))

  def testRegex(self):
    opt = option_lib.Option(name='<interface>')
    bm = option_lib.RegexMatch('[fgx]e-.*', 'A Juniper ethernet interface', opt)
    self.assertTrue(bm.Matches('ge-0/0/0'))
    self.assertFalse(bm.Matches('so-1/0/0'))

    self.assertEqual('ge-0/0/0', bm.GetMatch('ge-0/0/0'))
    self.assertEqual(None, bm.GetMatch('so-0/0/0'))

    self.assertEqual({'ge-0/0/0': 'A Juniper ethernet interface'},
                     bm.GetValidMatches('ge-0/0/0'))
    self.assertEqual({'<<interface>>':
                      'A Juniper ethernet interface ([fgx]e-.*)'},
                     bm.GetValidMatches(None))
    self.assertEqual({},
                     bm.GetValidMatches('so-0/0/0'))

  def testList(self):
    bm = option_lib.ListMatch(
        ['red', 'black', 'blue', 'blueish', 'green'], 'A colour',
        option_lib.Option('foo'))
    self.assertTrue(bm.Matches('red'))
    self.assertTrue(bm.Matches('blue'))
    self.assertFalse(bm.Matches('white'))

    self.assertEqual('blue', bm.GetMatch('blue'))
    self.assertEqual('blueish', bm.GetMatch('blueish'))
    self.assertEqual(None, bm.GetMatch('wh'))

    self.assertEqual({'blue': '', 'black': '',
                      'blueish': ''},
                     bm.GetValidMatches('bl'))
    self.assertEqual({'red': '',
                      'black': '',
                      'blue': '',
                      'blueish': '',
                      'green': ''},
                     bm.GetValidMatches(None))
    self.assertEqual({},
                     bm.GetValidMatches('wh'))

  def testListRegexMatch(self):
    bm = option_lib.ListMatch(['/wi*/', '/bo*/', 'foobar'], 'foo',
                              option_lib.Option('foo'))
    self.assertTrue(bm.Matches('w'))
    self.assertTrue(bm.Matches('wi'))
    self.assertTrue(bm.Matches('wiiiiiiiiiiii'))
    self.assertTrue(bm.Matches('b'))
    self.assertTrue(bm.Matches('bo'))
    self.assertTrue(bm.Matches('booooooooooooooo'))
    self.assertTrue(bm.Matches('foobar'))
    self.assertFalse(bm.Matches('zzzzzzz'))

    self.assertEqual('foobar', bm.GetMatch('fo'))
    self.assertEqual(None, bm.GetMatch('wiii'))

    self.assertEqual({'foobar': '', '/bo*/': '', '/wi*/': ''}, bm.GetValidMatches(''))
    self.assertEqual({}, bm.GetValidMatches('booo'))

  def testDict(self):
    bm = option_lib.DictMatch(
        {'red': 'The colour red',
         'black': 'The colour black',
         'blue': 'The colour blue',
         'blueish': 'A sort of blue',
         'green': 'The colour green'}, option_lib.Option('foo'))
    self.assertTrue(bm.Matches('red'))
    self.assertTrue(bm.Matches('blue'))
    self.assertTrue(bm.Matches('blueish'))
    self.assertFalse(bm.Matches('white'))

    self.assertEqual('blue', bm.GetMatch('blue'))
    self.assertEqual('blueish', bm.GetMatch('blueish'))
    self.assertEqual(None, bm.GetMatch('wh'))

    self.assertEqual({'blue': 'The colour blue',
                      'black': 'The colour black',
                      'blueish': 'A sort of blue'},
                     bm.GetValidMatches('bl'))
    self.assertEqual({'red': 'The colour red',
                      'black': 'The colour black',
                      'blue': 'The colour blue',
                      'blueish': 'A sort of blue',
                      'green': 'The colour green'},
                     bm.GetValidMatches(None))
    self.assertEqual({},
                     bm.GetValidMatches('wh'))

  def testDictRegexMatch(self):
    bm = option_lib.DictMatch(
        {'foobar': 'foobar',
         '/wi*/': 'hurray',
         '/bo*/': 'booooo'}, option_lib.Option('foo'))

    self.assertTrue(bm.Matches('foobar'))
    self.assertTrue(bm.Matches('w'))
    self.assertTrue(bm.Matches('wi'))
    self.assertTrue(bm.Matches('wiiii'))
    self.assertTrue(bm.Matches('b'))
    self.assertTrue(bm.Matches('boooooo'))
    self.assertFalse(bm.Matches('zzzzzzz'))

    self.assertEqual({'foobar': 'foobar',
                      '/wi*/': 'hurray',
                      '/bo*/': 'booooo'},
                     bm.GetValidMatches(None))
    self.assertEqual({'foobar': 'foobar',
                      '/wi*/': 'hurray',
                      '/bo*/': 'booooo'},
                     bm.GetValidMatches(''))
    self.assertEqual({},
                     bm.GetValidMatches('zzz'))
    self.assertEqual({'foobar': 'foobar'},
                     bm.GetValidMatches('fo'))

  def testMethod(self):
    def MatchMethod(option):
      return {
          'red': 'The colour red',
          'black': 'The colour black',
          'blue': 'The colour blue',
          'blueish': 'A sort of blue',
          'green': 'The colour green'}

    bm = option_lib.MethodMatch(MatchMethod, option_lib.Option('foo'))
    self.assertTrue(bm.Matches('red'))
    self.assertTrue(bm.Matches('blue'))
    self.assertTrue(bm.Matches('blueish'))
    self.assertFalse(bm.Matches('white'))

    self.assertEqual('blue', bm.GetMatch('blue'))
    self.assertEqual('blueish', bm.GetMatch('blueish'))
    self.assertEqual(None, bm.GetMatch('wh'))

    self.assertEqual({'blue': 'The colour blue',
                      'black': 'The colour black',
                      'blueish': 'A sort of blue'},
                     bm.GetValidMatches('bl'))
    self.assertEqual({'red': 'The colour red',
                      'black': 'The colour black',
                      'blue': 'The colour blue',
                      'blueish': 'A sort of blue',
                      'green': 'The colour green'},
                     bm.GetValidMatches(None))
    self.assertEqual({},
                     bm.GetValidMatches('wh'))

  def testPath(self):
    """Tests path matching."""
    fm = option_lib.PathMatch(None, None)
    self.assertTrue(fm.Matches('blah'))
    self.assertTrue(fm.Matches('/etc'))
    self.assertFalse(fm.Matches(''))
    self.assertFalse(fm.Matches(' '))

    fm = option_lib.PathMatch(None, option_lib.Option('foo'),
                              only_existing=True,
                              default_path='./testdata/')
    self.assertEqual(
        {'boo1': '', 'boo2': '', 'file1': ''},
        fm.GetValidMatches())

    self.assertEqual(
        {'file1': ''},
        fm.GetValidMatches('f'))

    self.assertEqual(
        {'boo1': '', 'boo2': ''},
        fm.GetValidMatches('bo'))

    self.assertTrue(fm.Matches('boo1'))
    self.assertFalse(fm.Matches('boo'))
    self.assertFalse(fm.Matches('blum'))

    self.assertEqual(None, fm.GetMatch('boo'))
    self.assertEqual('boo1', fm.GetMatch('boo1'))

    fm = option_lib.PathMatch(None, option_lib.Option('foo'),
                              only_existing=True,
                              only_dirs=True)

    self.assertEqual(
        {'testdata/': ''},
        fm.GetValidMatches())


if __name__ == '__main__':
  unittest.main()
