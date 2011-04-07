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

import squires

TEST_PATH = '.'

class CommandsTest(unittest.TestCase):

  def setUp(self):
    """First thing we do is build a command tree."""
    self.cmd = squires.Command()
    self.cmd.name = '<root>'

    self.cmd.AddCommand('show',
                        help='show help')

    interface = squires.Command()
    interface.name = 'interface'
    interface.help = 'interface help'
    interface.ancestors = ['show']
    self.cmd.Attach(interface)

    command = squires.Command()
    command.name = 'xe10'
    command.help = 'xe10 help'
    command.ancestors = ['show', 'interface']
    self.cmd.Attach(command)

    command = squires.Command()
    command.name = 'xe1'
    command.help = 'xe1 help'
    command.ancestors = ['show', 'interface']
    self.cmd.Attach(command)

    command = squires.Command()
    command.name = 'terse'
    command.help = 'terse help'
    command.ancestors = ['show', 'interface']
    self.cmd.Attach(command)

    command = squires.Command()
    command.name = 'version'
    command.help = 'version help'
    command.ancestors = ['show']
    self.cmd.Attach(command)

    interface.AddSubCommand('teal',
                            help='teal help')
    command = squires.Command()
    command.name = 'invisible'
    command.help = 'invisible command'
    command.hidden = True
    command.ancestors = ['show']
    self.cmd.Attach(command)

    command = squires.Command()
    command.name = 'logs'
    command.help = 'write file logs'
    command.ancestors = ['write', 'file']
    self.cmd.Attach(command)

  def testAttach(self):
    """Verify that commands get attached in the right place."""
    self.failUnlessEqual(self.cmd['show'].name, 'show')

    self.failUnlessEqual(self.cmd['show']['interface'].name, 'interface')

    self.failUnlessEqual(self.cmd['show']['interface']['terse'].name, 'terse')

    self.failUnlessEqual(self.cmd['show'].root, self.cmd)
    self.failUnlessEqual(self.cmd['show']['interface'].root, self.cmd)
    self.failUnlessEqual(self.cmd['show']['interface']['terse'].root, self.cmd)

    # Verify that _AddAncestors() has worked.
    self.failUnlessEqual('write', self.cmd['write'].name)
    self.failUnlessEqual('file', self.cmd['write']['file'].name)
    self.failUnlessEqual('logs', self.cmd['write']['file']['logs'].name)

    command = squires.Command()
    command.name = 'write'
    command.help = 'Write something'
    command.ancestors = []
    self.cmd.Attach(command)

    # Merge a new Command() over an existing.
    self.failUnlessEqual('write', self.cmd['write'].name)
    self.failUnlessEqual('file', self.cmd['write']['file'].name)
    self.failUnlessEqual('logs', self.cmd['write']['file']['logs'].name)

    command = squires.Command()
    command.name = 'file'
    command.help = 'Write file'
    command.ancestors = ['write']
    command.AddOption('now', helptext='Write it now')
    self.cmd.Attach(command)

    self.failUnlessEqual('write', self.cmd['write'].name)
    self.failUnlessEqual('file', self.cmd['write']['file'].name)
    self.failUnlessEqual('Write file', self.cmd['write']['file'].help)
    self.failUnlessEqual('logs', self.cmd['write']['file']['logs'].name)
    self.assertEqual(1, len(self.cmd['write']['file'].options))

  def testOption(self):
    """Test the Option() class."""
    option = squires.Option(name='foo', helptext='bar')
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
    option = squires.Option(name='<aid>', boolean=False,
                            match='\d[a-z]\d', helptext='bar')
    self.failUnlessEqual(option.Match(['2e2'], None), '2e2')
    self.failUnlessEqual(option.Match(['foobar', '2e2'], None), '2e2')
    self.failUnlessEqual(option.Match(['2e2', 'foobar'], None), '2e2')
    self.failUnlessEqual(option.Match(['e2e'], None), None)
    self.failUnlessEqual(option.Match(['e2e', 'foo'], None), None)

    # And boolean regex based options.
    option = squires.Option(name='<aid>', boolean=True,
                            match='\d[a-z]\d', helptext='bar')
    self.failUnlessEqual(option.Match(['2e2'], None), True)
    self.failUnlessEqual(option.Match(['foobar', '2e2'], None), True)
    self.failUnlessEqual(option.Match(['2e2', 'foobar'], None), True)
    self.failUnlessEqual(option.Match(['e2e'], None), None)
    self.failUnlessEqual(option.Match(['e2e', 'foo'], None), None)

  def testPositionalOption(self):
    cmd = self.cmd['show']['interface']
    cmd.AddOption(name='<primaryip>', match='.*',
                  position=0)
    cmd.AddOption(name='<secondaryip>', match='.*',
                  position=1)
    cmd.AddOption(name='<username>', match='.*',
                  position=2)
    cmd.AddOption(name='<filename>', match='.*',
                  position=3)

    cmd.command_line = ['1.1.1.1', '2.2.2.2', 'user', 'somefile']
    self.failUnlessEqual(cmd.GetOption('<primaryip>'), '1.1.1.1')
    self.failUnlessEqual(cmd.GetOption('<secondaryip>'), '2.2.2.2')
    self.failUnlessEqual(cmd.GetOption('<username>'), 'user')
    self.failUnlessEqual(cmd.GetOption('<filename>'), 'somefile')

    cmd.command_line = ['1.1.1.1', '2.2.2.2', 'user']
    self.failUnlessEqual(cmd.GetOption('<filename>'), None)

  def testGetGroupOption(self):
    """Test group options."""
    cmd = self.cmd['show']['interface']
    cmd.AddOption('terse', group='verbosity')
    cmd.AddOption('detailed', group='verbosity')
    cmd.AddOption('<int>', match='ge-.', group='interface')
    cmd.AddOption('all', boolean=False, group='interface')
    cmd.AddOption('hardware')

    # Empty commandline should match no groups.
    cmd.command_line = []
    self.failIf(cmd.GetGroupOption('verbosity'))
    self.failIf(cmd.GetGroupOption('hardware'))
    self.failIf(cmd.GetGroupOption('interface'))
    # Match a member of a group
    cmd.command_line = ['terse']
    self.failUnlessEqual(cmd.GetGroupOption('verbosity'), 'terse')
    self.failIf(cmd.GetGroupOption('interface'))
    # Same, but with an additional parameter.
    cmd.command_line = ['terse', 'all']
    self.failUnlessEqual(cmd.GetGroupOption('verbosity'), 'terse')
    self.failUnlessEqual(cmd.GetGroupOption('interface'), 'all')
    # Match a regex based group option
    cmd.command_line = ['terse', 'ge-1/3/0']
    self.failUnlessEqual(cmd.GetGroupOption('interface'), 'ge-1/3/0')
    cmd.command_line = ['ge-2/3/0']
    self.failUnlessEqual(cmd.GetGroupOption('interface'), 'ge-2/3/0')

  def testWithMethod(self):
    def MyMethod(*args):
      """test docstring"""
    cmd = squires.Command(name='foo', method=MyMethod)
    self.failUnlessEqual('test docstring',
                         cmd.help)

  def testDisambiguate(self):
    """Test we can disambiguate commands."""
    # Make sure we can get common prefixes.
    self.failUnlessEqual(
        self.cmd._GetCommonPrefix(['internal', 'inter']),
        'inter')
    self.failUnlessEqual(
        self.cmd._GetCommonPrefix(['intra', 'inter', 'interface']),
        'int')
    self.failUnlessEqual(
        self.cmd._GetCommonPrefix(['tense', 'terse', 'tyre']),
        't')
    self.failUnlessEqual(
        self.cmd._GetCommonPrefix(['tense', 'style', 'place']),
        '')
    self.failUnlessEqual(
        self.cmd._GetCommonPrefix(['2-A-4-T1-1', '2-A-4-T1-2']),
        '2-A-4-T1-')

    # Disambiguate single command
    self.failUnlessEqual(
        self.cmd.Disambiguate(['sho']),
        ['show'])

    # Disambiguate sub command
    self.failUnlessEqual(
        self.cmd.Disambiguate(['sho', 'inter']),
        ['show', 'interface'])

    # Multiple disambiguate down the tree, last one
    # is ambiguous.
    self.failUnlessEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'te']),
        ['show', 'interface', 'te'])
    # Similar, last one is not ambiguous
    self.failUnlessEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'ter']),
        ['show', 'interface', 'terse'])

    # Disambiguate when there is an exact match
    self.failUnlessEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'xe1'],
                              prefer_exact_match=True),
        ['show', 'interface', 'xe1'])
    # Disambiguate option completions
    self.cmd['show']['interface'].AddOption(name='text',
                                            helptext='text help')
    self.cmd['show']['interface'].AddOption(name='test',
                                            helptext='test help')
    self.cmd['show']['interface'].AddOption(name='detail',
                                            helptext='detail help')
    self.cmd['show']['interface'].AddOption(name='intf', keyvalue=True,
                                            match=['ge16', 'ge1', 'ge10'],
                                            helptext='intf help')
    self.cmd['show']['interface'].AddOption(name='level',
                                            keyvalue=True, match='\d+',
                                            helptext='detail help')

    self.failUnlessEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'ter']),
        ['show', 'interface', 'terse'])
    self.failUnlessEqual(
        self.cmd.Disambiguate(['sh', 'inter', 't']),
        ['show', 'interface', 'te'])
    self.failUnlessEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'intf', 'ge1'],
                              prefer_exact_match=True),
        ['show', 'interface', 'intf', 'ge1'])
    self.failUnlessEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'd', 'tex']),
        ['show', 'interface', 'detail', 'text'])
    self.failUnlessEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'd', 'te']),
        ['show', 'interface', 'detail', 'te'])

    self.failUnlessEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'le', '2']),
        ['show', 'interface', 'level', '2'])
    self.failUnlessEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'le', '2', 'te']),
        ['show', 'interface', 'level', '2', 'te'])
    self.failUnlessEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'tes', 'le', '2']),
        ['show', 'interface', 'test', 'level', '2'])
    self.failUnlessEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'tes', 'le']),
        ['show', 'interface', 'test', 'level'])

  def testRequired(self):
    """Test required options."""
    command = self.cmd['show']['version']
    command.AddOption('software')
    command.AddOption('hardware')
    command.AddOption('req1', required=True)
    command.AddOption('detailed', required=True, group='type')
    command.AddOption('terse', required=True, group='type')
    command.AddOption('lines', keyvalue=True, match='\d+')

    self.failIf(command.options.HasAllValidOptions([]))
    self.failIf(command.options.HasAllValidOptions(['detailed']))
    self.failIf(command.options.HasAllValidOptions(['detailed', 'terse']))
    self.failUnless(command.options.HasAllValidOptions(['detailed', 'req1']))

    # Duplicate option
    self.failIf(command.options.HasAllValidOptions(['detailed', 'req1', 'req1']))
    # Duplicate group option
    self.failIf(command.options.HasAllValidOptions(
        ['detailed', 'terse', 'req1']))
    # Missing required group
    self.failIf(command.options.HasAllValidOptions(['req1']))

    self.failIf(command.options.HasAllValidOptions(['software']))
    self.failUnless(command.options.HasAllValidOptions(
        ['detailed', 'req1', 'software']))
    self.failUnless(command.options.HasAllValidOptions(
        ['detailed', 'req1', 'software', 'hardware']))
    self.failUnless(command.options.HasAllValidOptions(
        ['detailed', 'req1', 'lines', '30', 'software', 'hardware']))
    self.failUnless(command.options.HasAllValidOptions(
        ['detailed', 'req1', 'software', 'hardware', 'lines', '30']))
    self.failIf(command.options.HasAllValidOptions(
        ['detailed', 'req1', 'lines', 'software', 'hardware']))
    self.failIf(command.options.HasAllValidOptions(
        ['detailed', 'req1', 'software', 'hardware', 'lines']))

  def testKeyValueOption(self):
    command = self.cmd['show']['version']

    # keyvalue must have 'required' or 'is_path'
    self.failUnlessRaises(
        ValueError, command.AddOption, 'lines', keyvalue=True)

    command.AddOption('lines', keyvalue=True, match='\d+')
    self.assertEqual('lines', command.options[0].name)
    self.assertEqual('<lines__arg>', command.options[1].name)

    self.assertTrue(command.options[0].keyvalue)
    self.assertTrue(command.options[0].boolean)
    self.assertTrue(command.options[1].keyvalue)

    self.assertEqual(command.options[1], command.options[0].arg_val)
    self.assertEqual(command.options[0], command.options[1].arg_key)
    self.assertTrue(command.options[0].match is None)

    self.assertTrue(command.options[0].Matches(['has', 'lines', '30'], 1))
    self.assertTrue(command.options[1].Matches(['has', 'lines', '30'], 2))
    self.assertFalse(command.options[0].Matches(['has', 'free', 'dd'], 1))
    self.assertFalse(command.options[1].Matches(['has', 'free', 'dd'], 2))

    cmd = self.cmd['show']['interface']
    cmd.AddOption('name', keyvalue=True, match='ge.*')
    cmd.command_line = ['show', 'interface', 'name', 'ge-0/0/0']
    self.failUnlessEqual('ge-0/0/0', cmd.GetOption('name'))
    cmd.command_line = ['show', 'interface', 'ge-0/0/0']
    self.assertTrue(cmd.GetOption('name') is None)

    cmd.AddOption('style', keyvalue=True, match=['short', 'long'])
    cmd.command_line = ['show', 'interface', 'style', 'lo']
    self.failUnlessEqual({'long': ''}, cmd.Completer(cmd.command_line))
    cmd.command_line = ['show', 'interface', 'style', 'short']
    self.failUnlessEqual('short', cmd.GetOption('style'))
    cmd.command_line = ['show', 'interface', 'style', 's']
    self.failUnlessEqual('short', cmd.GetOption('style'))
    cmd.command_line = ['show', 'interface', 'style', 'l']
    self.failUnlessEqual('long', cmd.GetOption('style'))

    cmd.AddOption('style', keyvalue=True, match={'short': 'Short style',
                                                 'long': 'Long style'},
                  default='long')
    cmd.AddOption('size', keyvalue=True, match={'small': 'Small size',
                                                 'long': 'Long size'})
    cmd.command_line = ['show', 'interface', 'style', 'short']
    self.failUnlessEqual('short', cmd.GetOption('style'))
    cmd.command_line = ['show', 'interface', 'style', 's']
    self.failUnlessEqual('short', cmd.GetOption('style'))
    cmd.command_line = ['show', 'interface', 'style', 'l']
    self.failUnlessEqual('long', cmd.GetOption('style'))

    cmd.command_line = ['show', 'interface', 'style', 'l']
    self.failUnlessEqual({'long': 'Long style'}, cmd.Completer(cmd.command_line))

    cmd.command_line = ['show', 'interface']
    self.failUnlessEqual('long', cmd.GetOption('style'))

    cmd.command_line = ['show', 'interface', 'style', 'long', 'size', 'l']
    self.failUnlessEqual({'long': 'Long size'}, cmd.Completer(cmd.command_line))
    cmd.command_line = ['show', 'interface', 'size', 'long', 'style', 'l']
    self.failUnlessEqual({'long': 'Long style'}, cmd.Completer(cmd.command_line))

    cmd.AddOption('count', keyvalue=True, match=lambda x: {'one': '1', 'two':
                                                           '2'})
    cmd.command_line = ['show', 'interface', 'count', 'o']
    self.failUnlessEqual({'one': '1'}, cmd.Completer(cmd.command_line))

    cmd.AddOption('colour', keyvalue=True, hidden=True, match=('red', 'blue'))
    cmd.command_line = ['show', 'interface', 'col']
    self.failUnlessEqual({}, cmd.Completer(cmd.command_line))
    cmd.command_line = ['show', 'interface', 'colour', 'red']
    self.failUnlessEqual('red', cmd.GetOption('colour'))

    cmd.command_line = ['show', 'interface', 'co']
    self.failUnlessEqual({'count': None}, cmd.Completer(cmd.command_line))

  def FakeReadlineGetBuffer(self):
    return self.fake_buffer

  def testReadlineCompleter(self):
    squires.readline.get_line_buffer = self.FakeReadlineGetBuffer

    self.fake_buffer = 'sh'
    self.failUnlessEqual(self.cmd.ReadlineCompleter('', 0),
                         'show ')
    self.fake_buffer = 'show vers'
    self.failUnlessEqual(self.cmd.ReadlineCompleter('', 0),
                         'version ')
    # Unterminated quote should still complete
    self.fake_buffer = 'show "vers'
    self.failUnlessEqual(self.cmd.ReadlineCompleter('', 0),
                         'version ')

    self.fake_buffer = 'show version '
    self.failUnlessEqual(self.cmd.ReadlineCompleter('', 0),
                         '')

    command = self.cmd['show']['version']
    command.AddOption('software')
    command.AddOption('hardware')
    self.fake_buffer = 'show version s'
    self.failUnlessEqual(self.cmd.ReadlineCompleter('', 0),
                         'software ')

  def testComplete(self):
    """Test command completion."""
    self.failUnlessEqual(
        self.cmd.Completer(['sh']),
        {'show': 'show help'})

    self.failUnlessEqual(
        self.cmd.Completer(['sh', 've']),
        {'version': 'version help'})

    self.failUnlessEqual(
        self.cmd.Completer(['show', 'interf']),
        {'interface': 'interface help'})

    self.failUnlessEqual(
        self.cmd.Completer(['show', 'interf', 'xe1']),
        {'xe1': 'xe1 help', 'xe10': 'xe10 help'})

    self.cmd['show']['interface'].runnable = True
    self.failUnlessEqual(
        self.cmd.Completer(['show', 'interface', ' ']),
        {'terse': 'terse help', 'teal': 'teal help',
         'xe1': 'xe1 help', 'xe10': 'xe10 help',
         '<cr>': self.cmd.execute_command_string})

    self.cmd['show']['interface']['terse'].runnable = True
    self.failUnlessEqual(
        self.cmd.Completer(['show', 'interface', 'terse', ' ']),
        {'<cr>': self.cmd.execute_command_string})

    completions = self.cmd.Completer(['show', 'interf', 'te'])
    self.failUnlessEqual(completions['terse'], 'terse help')
    self.failUnlessEqual(completions['teal'], 'teal help')

    completions = self.cmd.Completer(['show', 'interf', 'tea'])
    self.failUnlessEqual(completions['teal'], 'teal help')

    completions = self.cmd.Completer(['SHOW', 'INTERF', 'TE'])
    self.failUnlessEqual(completions['terse'], 'terse help')
    self.failUnlessEqual(completions['teal'], 'teal help')

    completions = self.cmd.Completer(['show', 'invi'])
    self.failUnlessEqual({}, completions)
    self.cmd['show']['invisible'].hidden = False
    completions = self.cmd.Completer(['show', 'invi'])
    self.failUnlessEqual({'invisible': 'invisible command'}, completions)

  def testFileCompleter(self):
    # TODO (bbuxton): Re-enable these tests.
    return
    uncompleted = os.path.join(TEST_PATH, 'testdata/', 'fi')
    self.failUnlessEqual(self.cmd.options.FileCompleter(uncompleted),
                         [os.path.join(TEST_PATH, 'testdata/', 'file1')])

    uncompleted = os.path.join(TEST_PATH, 'testdata/', 'file1')
    self.failUnlessEqual(self.cmd.options.FileCompleter(uncompleted),
                         [os.path.join(TEST_PATH, 'testdata/', 'file1')])

    uncompleted = os.path.join(TEST_PATH, 'testda')
    self.failUnlessEqual(self.cmd.options.FileCompleter(uncompleted,
                                                        only_dirs=True),
                         [os.path.join(TEST_PATH, 'testdata/')])

    self.failUnlessEqual(self.cmd.options.FileCompleter(
        'fil', default_path='testdata/'), ['file1'])

    uncompleted = os.path.join(TEST_PATH, 'testdata/', 'boo1')
    self.failUnlessEqual(self.cmd.options.FileCompleter(uncompleted),
                         [os.path.join(TEST_PATH, 'testdata/', 'boo1')])

    uncompleted = os.path.join(TEST_PATH, 'testdata/', 'b')
    self.failUnlessEqual(sorted(self.cmd.options.FileCompleter(uncompleted)),
                         [os.path.join(TEST_PATH, 'testdata/', 'boo1'),
                          os.path.join(TEST_PATH, 'testdata/', 'boo2')],
                        )

    uncompleted = os.path.join(TEST_PATH, 'testdata/', 'c')
    self.failUnlessEqual(self.cmd.options.FileCompleter(uncompleted), [])

  def testOptionCompletes(self):
    # Extra option completions
    self.cmd['show']['interface'].AddOption(name='text', helptext='text help')
    self.cmd['show']['interface'].AddOption(name='test',
                                            helptext='test help')
    self.cmd['show']['interface'].AddOption(name='detail',
                                            helptext='detail help',
                                            group='type')
    self.cmd['show']['interface'].AddOption(name='extensive',
                                            helptext='extensive help',
                                            group='type')
    self.cmd['show']['interface'].AddOption(name='lines',
                                            helptext='lines to show',
                                            keyvalue=True,
                                            default=25,
                                            match='\d+')

    # Test two options
    self.failUnlessEqual(
        self.cmd['show']['interface'].options.GetOptionCompletes(['te']),
        {'text': 'text help', 'test': 'test help'})
    # Test one option
    self.failUnlessEqual(
        self.cmd['show']['interface'].options.GetOptionCompletes(['de']),
        {'detail': 'detail help'})
    # Test that pre-existing option is not included in completes
    self.failUnlessEqual(
        self.cmd['show']['interface'].options.GetOptionCompletes(['tex', 'de']),
        {'detail': 'detail help'})
    # Same, but two results
    self.failUnlessEqual(
        self.cmd['show']['interface'].options.GetOptionCompletes(['de', 'te']),
        {'test': 'test help', 'text': 'text help'})
    # All options should be returned
    self.failUnlessEqual(
        self.cmd['show']['interface'].options.GetOptionCompletes([' ']),
        {'text': 'text help', 'test': 'test help', 'detail': 'detail help',
         'extensive': 'extensive help',
         'lines': 'lines to show [Default: 25]'})
    # A group member already present, excluded other groups members
    # from completes
    self.failUnlessEqual(
        self.cmd['show']['interface'].options.GetOptionCompletes(['de', ' ']),
        {'test': 'test help', 'text': 'text help',
         'lines': 'lines to show [Default: 25]'})

    # All available subcommands and options.
    self.failUnlessEqual(
        self.cmd['show']['interface'].Completer([' ']),
        {'terse': 'terse help', 'teal': 'teal help',
         'text': 'text help',
         'test': 'test help', 'detail': 'detail help',
         'extensive': 'extensive help',
         'xe1': 'xe1 help', 'xe10': 'xe10 help',
         'lines': 'lines to show [Default: 25]'})

    # Some matching subcommands and options
    self.failUnlessEqual(
        self.cmd['show']['interface'].Completer(['te']),
        {'terse': 'terse help', 'teal': 'teal help',
         'text': 'text help', 'test': 'test help'})
    # One matching subcommand
    self.failUnlessEqual(
        self.cmd['show']['interface'].Completer(['ter']),
        {'terse': 'terse help'})
    # One matching option, with existing option
    self.failUnlessEqual(
        self.cmd['show']['interface'].Completer(['tex', 'de']),
        {'detail': 'detail help'})
    # One matching option, with existing option, attempt to
    # add existing group member.
    self.failIf(
        self.cmd['show']['interface'].Completer(['tex', 'de', 'ex']))

    # Only non-included options are returned
    self.failUnlessEqual(
        self.cmd['show']['interface'].Completer(['tex', ' ']),
        {'test': 'test help', 'detail': 'detail help',
         'extensive': 'extensive help',
         'lines': 'lines to show [Default: 25]'})

    # KeyValue options
    self.failUnlessEqual(
        self.cmd['show']['interface'].Completer(['lin']),
        {'lines': 'lines to show [Default: 25]'})
    self.failUnlessEqual(
        self.cmd['show']['interface'].Completer(['lin', ' ']),
        {'<lines>': 'lines to show [Default: 25]'})
    self.failUnlessEqual(
        self.cmd['show']['interface'].Completer(['tex', 'lin', ' ']),
        {'<lines>': 'lines to show [Default: 25]'})


if __name__ == '__main__':
  unittest.main()
