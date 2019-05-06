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

import io
import os
import sys
import tempfile
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
    self.assertEqual(self.cmd['show'].name, 'show')

    self.assertEqual(self.cmd['show']['interface'].name, 'interface')

    self.assertEqual(self.cmd['show']['interface']['terse'].name, 'terse')

    self.assertEqual(self.cmd['show'].root, self.cmd)
    self.assertEqual(self.cmd['show']['interface'].root, self.cmd)
    self.assertEqual(self.cmd['show']['interface']['terse'].root, self.cmd)

    self.assertEqual(['show', 'interface', 'terse'],
                         self.cmd['show']['interface']['terse'].path)

    # Verify that _AddAncestors() has worked.
    self.assertEqual('write', self.cmd['write'].name)
    self.assertEqual('file', self.cmd['write']['file'].name)
    self.assertEqual('logs', self.cmd['write']['file']['logs'].name)

    command = squires.Command()
    command.name = 'write'
    command.help = 'Write something'
    command.ancestors = []
    self.cmd.Attach(command)

    # Merge a new Command() over an existing.
    self.assertEqual('write', self.cmd['write'].name)
    self.assertEqual('file', self.cmd['write']['file'].name)
    self.assertEqual('logs', self.cmd['write']['file']['logs'].name)

    command = squires.Command()
    command.name = 'file'
    command.help = 'Write file'
    command.ancestors = ['write']
    command.AddOption('now', helptext='Write it now')
    self.cmd.Attach(command)

    self.assertEqual('now', command.options.GetOptionObject('now').name)
    self.assertEqual(None, command.options.GetOptionObject('unknown'))

    self.assertEqual('write', self.cmd['write'].name)
    self.assertEqual('file', self.cmd['write']['file'].name)
    self.assertEqual('Write file', self.cmd['write']['file'].help)
    self.assertEqual('logs', self.cmd['write']['file']['logs'].name)
    self.assertEqual(1, len(self.cmd['write']['file'].options))

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
    self.assertEqual(cmd.GetOption('<primaryip>'), '1.1.1.1')
    self.assertEqual(cmd.GetOption('<secondaryip>'), '2.2.2.2')
    self.assertEqual(cmd.GetOption('<username>'), 'user')
    self.assertEqual(cmd.GetOption('<filename>'), 'somefile')

    cmd.command_line = ['1.1.1.1', '2.2.2.2', 'user']
    self.assertEqual(cmd.GetOption('<filename>'), None)

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
    self.assertFalse(cmd.GetGroupOption('verbosity'))
    self.assertFalse(cmd.GetGroupOption('hardware'))
    self.assertFalse(cmd.GetGroupOption('interface'))
    # Match a member of a group
    cmd.command_line = ['terse']
    self.assertEqual(cmd.GetGroupOption('verbosity'), 'terse')
    self.assertFalse(cmd.GetGroupOption('interface'))
    # Same, but with an additional parameter.
    cmd.command_line = ['terse', 'all']
    self.assertEqual(cmd.GetGroupOption('verbosity'), 'terse')
    self.assertEqual(cmd.GetGroupOption('interface'), 'all')
    # Match a regex based group option
    cmd.command_line = ['terse', 'ge-1/3/0']
    self.assertEqual(cmd.GetGroupOption('interface'), 'ge-1/3/0')
    cmd.command_line = ['ge-2/3/0']
    self.assertEqual(cmd.GetGroupOption('interface'), 'ge-2/3/0')

  def testWithMethod(self):
    def MyMethod(*args):
      """test docstring."""
    cmd = squires.Command(name='foo', method=MyMethod)
    self.assertEqual('test docstring.',
                         cmd.help)

  def testDisambiguate(self):
    """Test we can disambiguate commands."""
    # Make sure we can get common prefixes.
    self.assertEqual(
        self.cmd._GetCommonPrefix(['internal', 'inter']),
        'inter')
    self.assertEqual(
        self.cmd._GetCommonPrefix(['intra', 'inter', 'interface']),
        'int')
    self.assertEqual(
        self.cmd._GetCommonPrefix(['tense', 'terse', 'tyre']),
        't')
    self.assertEqual(
        self.cmd._GetCommonPrefix(['tense', 'style', 'place']),
        '')
    self.assertEqual(
        self.cmd._GetCommonPrefix(['2-A-4-T1-1', '2-A-4-T1-2']),
        '2-A-4-T1-')

    # Disambiguate single command
    self.assertEqual(
        self.cmd.Disambiguate(['sho']),
        ['show'])

    # Disambiguate sub command
    self.assertEqual(
        self.cmd.Disambiguate(['sho', 'inter']),
        ['show', 'interface'])

    # Multiple disambiguate down the tree, last one
    # is ambiguous.
    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'te']),
        ['show', 'interface', 'te'])
    # Similar, last one is not ambiguous
    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'ter']),
        ['show', 'interface', 'terse'])

    # Disambiguate when there is an exact match
    self.assertEqual(
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

    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'ter']),
        ['show', 'interface', 'terse'])
    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 't']),
        ['show', 'interface', 'te'])
    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'intf', 'ge1'],
                              prefer_exact_match=True),
        ['show', 'interface', 'intf', 'ge1'])
    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'd', 'tex']),
        ['show', 'interface', 'detail', 'text'])
    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'd', 'te']),
        ['show', 'interface', 'detail', 'te'])

    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'le', '2']),
        ['show', 'interface', 'level', '2'])
    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'le', '2', 'te']),
        ['show', 'interface', 'level', '2', 'te'])
    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'tes', 'le', '2']),
        ['show', 'interface', 'test', 'level', '2'])
    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'tes', 'le']),
        ['show', 'interface', 'test', 'level'])
    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'intf', 'ge1']),
        ['show', 'interface', 'intf', 'ge1'])
    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'intf', 'ge']),
        ['show', 'interface', 'intf', 'ge'])
    self.assertEqual(
        self.cmd.Disambiguate(['sh', 'inter', 'ters', 'ters']),
        ['show', 'interface', 'terse', 'ters'])

  def testMultiword(self):
    cmd = self.cmd['show']['interface']
    cmd.AddOption('software')
    cmd.AddOption('description', keyvalue=True,
                  match='.+', multiword=True)
    cmd.AddOption('name', match='[xg]e-.*')

    cmd.command_line = ['software']
    self.assertEqual(None, cmd.GetOption('description'))
    self.assertEqual(None, cmd.GetOption('name'))
    self.assertTrue(cmd.GetOption('software'))
    cmd.command_line = ['software', 'description', 'A', 'fast', 'interface']
    self.assertTrue(cmd.GetOption('software'))
    self.assertEqual('A fast interface', cmd.GetOption('description'))
    cmd.command_line = ['xe-0/0/0', 'description', 'A', 'fast', 'interface']
    self.assertEqual('xe-0/0/0', cmd.GetOption('name'))
    self.assertEqual('A fast interface', cmd.GetOption('description'))

  def testRequired(self):
    """Test required options."""
    command = self.cmd['show']['version']
    command.AddOption('software')
    command.AddOption('hardware')
    command.AddOption('req1', required=True)
    command.AddOption('detailed', required=True, group='type')
    command.AddOption('with', required=True, keyvalue=True,
                      match=['all', 'nonw'])
    command.AddOption('terse', required=True, group='type')
    command.AddOption('lines', keyvalue=True, match='\d+')
    command.AddOption('blah', boolean=False, match='\S+')
    command.AddOption('frub', boolean=False, keyvalue=True, match='\S+')

    self.assertFalse(command.options.HasAllValidOptions([]))
    self.assertFalse(command.options.HasAllValidOptions(['detailed']))
    self.assertFalse(command.options.HasAllValidOptions(['detailed', 'terse']))
    self.assertTrue(command.options.HasAllValidOptions(
        ['detailed', 'req1', 'with', 'all']))

    # make sure keyvalue pair doesnt get used for other options.
    self.assertTrue(command.options.HasAllValidOptions(
        ['req1', 'detailed', 'with', 'all', 'frub', 'five', 'foobar']))

    # Missing required group
    self.assertFalse(command.options.HasAllValidOptions(['req1']))

    self.assertFalse(command.options.HasAllValidOptions(['software']))
    self.assertTrue(command.options.HasAllValidOptions(
        ['detailed', 'req1', 'with', 'all', 'software']))
    self.assertTrue(command.options.HasAllValidOptions(
        ['detailed', 'req1', 'with', 'all', 'software', 'hardware']))
    self.assertTrue(command.options.HasAllValidOptions(
        ['detailed', 'req1', 'with', 'all', 'lines', '30',
         'software', 'hardware']))
    self.assertTrue(command.options.HasAllValidOptions(
        ['detailed', 'req1', 'with', 'all', 'software',
         'hardware', 'lines', '30']))
    self.assertFalse(command.options.HasAllValidOptions(
        ['detailed', 'req1', 'with', 'all', 'lines', 'software', 'hardware']))
    self.assertFalse(command.options.HasAllValidOptions(
        ['detailed', 'req1', 'with', 'all', 'software', 'hardware', 'lines']))

  def testKeyValueOption(self):
    command = self.cmd['show']['version']

    # keyvalue must have 'required' or 'is_path'
    self.assertRaises(
        ValueError, command.AddOption, 'lines', keyvalue=True)

    command.AddOption('lines', keyvalue=True, match='\d+')
    self.assertEqual('lines', command.options[0].name)
    self.assertEqual('<lines__arg>', command.options[1].name)

    self.assertTrue(command.options[0].keyvalue)
    self.assertTrue(command.options[0].boolean)
    self.assertTrue(command.options[1].keyvalue)

    self.assertEqual(command.options[1], command.options[0].arg_val)
    self.assertEqual(command.options[0], command.options[1].arg_key)
    self.assertTrue(command.options[0].matcher.MATCH == 'boolean')

    self.assertTrue(command.options[0].FindMatches(
        ['has', 'lines', '30'], 1).valid)
    self.assertTrue(command.options[1].FindMatches(
        ['has', 'lines', '30'], 2).valid)
    self.assertFalse(command.options[0].FindMatches(
        ['has', 'free', 'dd'], 1).valid)
    self.assertFalse(command.options[1].FindMatches(
        ['has', 'free', 'dd'], 2).valid)

    cmd = self.cmd['show']['interface']
    cmd.AddOption('name', keyvalue=True, match='ge.*')
    cmd.command_line = ['name', 'ge-0/0/0']
    self.assertEqual('ge-0/0/0', cmd.GetOption('name'))
    cmd.command_line = ['ge-0/0/0']
    self.assertTrue(cmd.GetOption('name') is None)

    cmd.AddOption('style', keyvalue=True, match=['short', 'long'])
    cmd.command_line = ['style', 'lo']
    self.assertEqual({'long': ''}, cmd.Completer(cmd.command_line))
    cmd.command_line = ['style', 'short']
    self.assertEqual('short', cmd.GetOption('style'))
    cmd.command_line = ['style', 's']
    self.assertEqual('short', cmd.GetOption('style'))
    cmd.command_line = ['style', 'l']
    self.assertEqual('long', cmd.GetOption('style'))

    cmd.AddOption('style', keyvalue=True, match={'short': 'Short style',
                                                 'long': 'Long style'},
                  default='long')
    cmd.AddOption('size', keyvalue=True, match={'small': 'Small size',
                                                'long': 'Long size'})
    cmd.command_line = ['style', 'short']
    self.assertEqual('short', cmd.GetOption('style'))
    cmd.command_line = ['style', 's']
    self.assertEqual('short', cmd.GetOption('style'))
    cmd.command_line = ['style', 'l']
    self.assertEqual('long', cmd.GetOption('style'))

    cmd.command_line = ['style', 'l']
    self.assertEqual({'long': 'Long style [Default]'},
                         cmd.Completer(cmd.command_line))

    cmd.command_line = []
    self.assertEqual('long', cmd.GetOption('style'))

    cmd.command_line = ['style', 'long', 'size', 'l']
    self.assertEqual({'long': 'Long size'}, cmd.Completer(cmd.command_line))
    cmd.command_line = ['size', 'long', 'style', 'l']
    self.assertEqual({'long': 'Long style [Default]'},
                         cmd.Completer(cmd.command_line))

    cmd.AddOption('count', keyvalue=True, match=lambda x: {'one': '1', 'two':
                                                           '2'})
    cmd.command_line = ['count', 'o']
    self.assertEqual({'one': '1'}, cmd.Completer(cmd.command_line))

    cmd.AddOption('colour', keyvalue=True, hidden=True, match=('red', 'blue'))
    cmd.command_line = ['col']
    self.assertEqual({}, cmd.Completer(cmd.command_line))
    cmd.command_line = ['colour', 'red']
    self.assertEqual('red', cmd.GetOption('colour'))

    cmd.command_line = ['co']
    self.assertEqual({'count': None}, cmd.Completer(cmd.command_line))

  def FakeReadlineGetBuffer(self):
    return self.fake_buffer

  def testReadlineHistorySaving(self):
    for _ in range(squires.readline.get_current_history_length()):
      squires.readline.remove_history_item(0)

    cmd = squires.Command()
    cmd._SaveHistory()
    self.assertEqual([], cmd._saved_history)
    cmd._RestoreHistory()
    self.assertEqual(0, squires.readline.get_current_history_length())
    squires.readline.add_history('command one')
    squires.readline.add_history('command two')
    squires.readline.add_history('command three')
    cmd._SaveHistory()
    self.assertEqual(['command one', 'command two', 'command three'],
                     cmd._saved_history)
    self.assertEqual(0, squires.readline.get_current_history_length())
    # Child command history item, should be removed.
    squires.readline.add_history('command four')
    cmd._RestoreHistory()
    self.assertEqual(3, squires.readline.get_current_history_length())
    self.assertEqual('command one', squires.readline.get_history_item(1))
    self.assertEqual('command two', squires.readline.get_history_item(2))
    self.assertEqual('command three', squires.readline.get_history_item(3))

  def testReadlineCompleter(self):
    get_line_buffer = squires.readline.get_line_buffer
    squires.readline.get_line_buffer = self.FakeReadlineGetBuffer

    self.fake_buffer = 'sh'
    self.assertEqual(self.cmd.ReadlineCompleter('sh', 0), 'show' +
                         squires.COMPLETE_SUFFIX)
    self.fake_buffer = 'show vers'
    self.assertEqual(self.cmd.ReadlineCompleter('vers', 0), 'version' +
                         squires.COMPLETE_SUFFIX)
    # Unterminated quote should still complete
    self.fake_buffer = 'show "vers'
    self.assertEqual(self.cmd.ReadlineCompleter('"vers', 0), 'version' +
                         squires.COMPLETE_SUFFIX)

    self.fake_buffer = 'show version '
    self.assertEqual(self.cmd.ReadlineCompleter(' ', 0), None)

    command = self.cmd['show']['version']
    command.AddOption('software')
    command.AddOption('hardware')
    self.fake_buffer = 'show version s'
    self.assertEqual(self.cmd.ReadlineCompleter('s', 0), 'software' +
                         squires.COMPLETE_SUFFIX)
    squires.readline.get_line_buffer = get_line_buffer

  def testComplete(self):
    """Test command completion."""
    self.assertEqual(
        self.cmd.Completer(['sh']),
        {'show': 'show help'})

    self.assertEqual(
        self.cmd.Completer(['sh', 've']),
        {'version': 'version help'})

    self.assertEqual(
        self.cmd.Completer(['show', 'interf']),
        {'interface': 'interface help'})

    self.assertEqual(
        self.cmd.Completer(['show', 'interf', 'xe1']),
        {'xe1': 'xe1 help', 'xe10': 'xe10 help'})

    self.cmd['show']['interface'].runnable = True
    self.assertEqual(
        self.cmd.Completer(['show', 'interface', ' ']),
        {'terse': 'terse help', 'teal': 'teal help',
         'xe1': 'xe1 help', 'xe10': 'xe10 help',
         '<cr>': self.cmd.execute_command_string})

    self.cmd['show']['interface']['terse'].runnable = True
    self.assertEqual(
        self.cmd.Completer(['show', 'interface', 'terse', ' ']),
        {'<cr>': self.cmd.execute_command_string})

    completions = self.cmd.Completer(['show', 'interf', 'te'])
    self.assertEqual(completions['terse'], 'terse help')
    self.assertEqual(completions['teal'], 'teal help')

    completions = self.cmd.Completer(['show', 'interf', 'tea'])
    self.assertEqual(completions['teal'], 'teal help')

    completions = self.cmd.Completer(['SHOW', 'INTERF', 'TE'])
    self.assertEqual(completions['terse'], 'terse help')
    self.assertEqual(completions['teal'], 'teal help')

    completions = self.cmd.Completer(['show', 'invi'])
    self.assertEqual({}, completions)
    self.cmd['show']['invisible'].hidden = False
    completions = self.cmd.Completer(['show', 'invi'])
    self.assertEqual({'invisible': 'invisible command'}, completions)

  def testOptionCompletes(self):
    # Extra option completions
    self.cmd['show']['interface'].AddOption(name='text', helptext='text help')
    self.cmd['show']['interface'].AddOption(name='test',
                                            helptext='test help')
    self.cmd['show']['interface'].AddOption(
        name='detail', helptext='detail help', group='type')
    self.cmd['show']['interface'].AddOption(
        name='extensive', helptext='extensive help', group='type')
    self.cmd['show']['interface'].AddOption(
        name='name', helptext='Name of interface', keyvalue=True,
        match='\S+', group='ifspec')
    self.cmd['show']['interface'].AddOption(
        name='index', helptext='Index of interface', keyvalue=True,
        match='\S+', group='ifspec')
    self.cmd['show']['interface'].AddOption(
        name='lines', helptext='lines to show', keyvalue=True,
        default=25, match='\d+')

    # Test two options
    self.assertEqual(
        self.cmd['show']['interface'].options.GetOptionCompletes(['te']),
        {'text': 'text help', 'test': 'test help'})
    # Test one option
    self.assertEqual(
        self.cmd['show']['interface'].options.GetOptionCompletes(['de']),
        {'detail': 'detail help'})
    # Test that pre-existing option is not included in completes
    self.assertEqual(
        self.cmd['show']['interface'].options.GetOptionCompletes(['tex', 'de']),
        {'detail': 'detail help'})
    # Same, but two results
    self.assertEqual(
        self.cmd['show']['interface'].options.GetOptionCompletes(['de', 'te']),
        {'test': 'test help', 'text': 'text help'})

    # All options should be returned
    keys = ['detail', 'extensive', 'index', 'lines', 'name', 'test', 'text']
    values = ['Index of interface', 'Name of interface', 'detail help',
              'extensive help', 'lines to show', 'test help', 'text help',]
    res = self.cmd['show']['interface'].options.GetOptionCompletes([' '])
    self.assertEqual(keys, sorted(res.keys()))
    self.assertEqual(values, sorted(res.values()))

    # A group member already present, excluded other groups members
    # from completes
    keys = ['index', 'lines', 'name', 'test', 'text']
    values = ['Index of interface', 'Name of interface', 'lines to show',
              'test help', 'text help']
    res = self.cmd['show']['interface'].options.GetOptionCompletes(['de', ' '])
    self.assertEqual(keys, sorted(res.keys()))
    self.assertEqual(values, sorted(res.values()))

    # All available subcommands and options.
    keys = ['detail', 'extensive', 'index', 'lines', 'name', 'teal',
            'terse', 'test', 'text', 'xe1', 'xe10']
    values = ['Index of interface', 'Name of interface', 'detail help',
              'extensive help', 'lines to show', 'teal help',
              'terse help', 'test help', 'text help', 'xe1 help', 'xe10 help']
    res = self.cmd['show']['interface'].Completer([' '])
    self.assertEqual(keys, sorted(res.keys()))
    self.assertEqual(values, sorted(res.values()))

    # Some matching subcommands and options
    keys = ['teal', 'terse', 'test', 'text',]
    values = ['teal help', 'terse help', 'test help', 'text help']
    res = self.cmd['show']['interface'].Completer(['te'])
    self.assertEqual(keys, sorted(res.keys()))
    self.assertEqual(values, sorted(res.values()))

    # One matching subcommand
    self.assertEqual(
        self.cmd['show']['interface'].Completer(['ter']),
        {'terse': 'terse help'})
    # One matching option, with existing option
    self.assertEqual(
        self.cmd['show']['interface'].Completer(['tex', 'de']),
        {'detail': 'detail help'})
    # One matching option, with existing option, attempt to
    # add existing group member.
    self.assertFalse(
        self.cmd['show']['interface'].Completer(['tex', 'de', 'ex']))

    # Only non-included options are returned
    keys = ['detail', 'extensive', 'index', 'lines', 'name', 'test']
    values = ['Index of interface', 'Name of interface', 'detail help',
              'extensive help', 'lines to show', 'test help']
    res = self.cmd['show']['interface'].Completer(['tex', ' '])
    self.assertEqual(keys, sorted(res.keys()))
    self.assertEqual(values, sorted(res.values()))

    # KeyValue options
    self.assertEqual(
        self.cmd['show']['interface'].Completer(['lin']),
        {'lines': 'lines to show'})
    self.assertEqual(
        self.cmd['show']['interface'].Completer(['lin', ' ']),
        {'<lines>': 'lines to show [Default: 25]'})
    self.assertEqual(
        self.cmd['show']['interface'].Completer(['tex', 'lin', ' ']),
        {'<lines>': 'lines to show [Default: 25]'})
    # One with a group.
    self.assertEqual(
        self.cmd['show']['interface'].Completer(['index', ' ']),
        {'<index>': 'Index of interface'})
    self.assertEqual(
        self.cmd['show']['interface'].Completer(['index', '123', ' ']),
        {'detail': 'detail help',
         'extensive': 'extensive help',
         'lines': 'lines to show',
         'test': 'test help',
         'text': 'text help'})

  def testReadlineFuncs(self):
    root = squires.Command('<root>')
    root.AddCommand('one', help='ONE', method=squires)
    root.AddCommand('two', help='TWO', method=squires).AddSubCommand(
        'four', help='FOUR', method=squires)
    root.AddCommand('three', help='THREE', method=squires)
    # Test 'preparereadline'
    self.assertEqual(None, squires.readline.get_completer())
    self.assertFalse(' ' == squires.readline.get_completer_delims())
    root._ReadlinePrepare()
    self.assertEqual(root.ReadlineCompleter, squires.readline.get_completer())
    self.assertEqual(' ', squires.readline.get_completer_delims())
    root._ReadlineUnprepare()
    self.assertEqual(None, squires.readline.get_completer())
    self.assertFalse(' ' == squires.readline.get_completer_delims())

    get_line_buffer = squires.readline.get_line_buffer
    squires.readline.get_line_buffer = lambda: ''
    # Test 'FindCurrentCandidates'
    self.assertEqual({'one': 'ONE', 'two': 'TWO', 'three': 'THREE'},
                     root.FindCurrentCandidates())
    squires.readline.get_line_buffer = get_line_buffer
    squires.readline.insert_text('t')
    self.assertEqual({'two': 'TWO', 'three': 'THREE'},
                     root.FindCurrentCandidates())

    # Test completion formatter
    buf = io.StringIO()
    sys.stdout = buf
    root.FormatCompleterOptions('t', ['two', 'three'], 1)
    sys.stdout = sys.__stdout__
    self.assertEqual(
        ['', 'Valid completions:', ' three                 THREE',
         ' two                   TWO', '> t'],
        buf.getvalue().splitlines())

    self.assertEqual('three' + squires.COMPLETE_SUFFIX, root.ReadlineCompleter('', 0))
    self.assertEqual('two' + squires.COMPLETE_SUFFIX, root.ReadlineCompleter('', 1))
    self.assertEqual(None, root.ReadlineCompleter('', 2))

  def testParseTree(self):
    COMMAND = squires.CommandDefinition
    OPTION = squires.OptionDefinition

    cmd = COMMAND('foo', help='bar', method=squires)
    self.assertEqual(('foo',), cmd.args)
    self.assertEqual({'help': 'bar', 'method': squires}, cmd.kwargs)

    root = squires.Command('one')
    tree = {
        COMMAND('two', help='Number two', method=squires): {}
    }
    squires.ParseTree(root, tree)
    self.assertEqual('Number two', root['two'].help)

    root = squires.Command('<root>')
    tree = {
        COMMAND('one', help='Number one', method=squires): {
            OPTION('fast', boolean=True, helptext='Quickly'): {},
            OPTION('slow', boolean=True, helptext='Slowly'): {},
        },
        COMMAND('two', help='Number two', method=squires): {
            COMMAND('three', help='Number three', method=squires): {}
        }
    }
    squires.ParseTree(root, tree)
    self.assertEqual('Number two', root['two'].help)
    self.assertEqual('Number three', root['two']['three'].help)
    self.assertTrue(root['one'].options[0].helptext in ('Quickly', 'Slowly'))
    self.assertTrue(root['one'].options[1].helptext in ('Quickly', 'Slowly'))

  def testPipe(self):
    class testPipe(squires.pipe.Pipe):
      pass

    COMMAND = squires.CommandDefinition
    PIPE = squires.PipeDefinition
    PIPETREE = squires.PipeTreeDefinition
    OPTION = squires.OptionDefinition
    pipe1 = {
        PIPE('grep', pipe=testPipe()): {}
    }
    tree = {
        COMMAND('one', method=squires, help='ONE'): {
            OPTION('slow', boolean=True): {},
            PIPETREE(tree=pipe1): {},
        },
        COMMAND('two', method=squires, help='TWO'): {
            PIPETREE(tree=pipe1): {},
            COMMAND('four', method=squires, help='FOUR'): {},
        },
        COMMAND('three', method=squires, help='THREE'): {}
    }
    # Test that pipes get added to the tree, and can be found.
    root = squires.Command('<root>')
    squires.ParseTree(root, tree)
    self.assertEqual(None, root['three'].GetPipeTree())
    self.assertEqual('grep', root['one'].GetPipeTree()['grep'].name)
    self.assertTrue(isinstance(root['one'].GetPipeTree()['grep'].pipe,
                               testPipe))

    root['one'].command_line = ['slow', '|', 'grep', 'bar']
    self.assertTrue(root['one'].GetOption('slow'))
    root['one'].command_line = ['|', 'grep', 'slow']
    self.assertIsNone(root['one'].GetOption('slow'))

    # Test 'WillPipe()'
    self.assertTrue(root['two']['four'].WillPipe(
        ['two', 'four', squires.PIPE_CHAR, 'grep']))
    self.assertFalse(root['two']['four'].WillPipe(
        ['two', 'four', 'grep']))

  def testSplitCommandLine(self):
    expected_tokens = ['command', 'subcommand', 'parameter', '|', 'pipe']

    command = 'command subcommand parameter | pipe'
    tokens = self.cmd._SplitCommandLine(command)
    self.assertEqual(tokens, expected_tokens)

    command = 'command subcommand parameter| pipe'
    tokens = self.cmd._SplitCommandLine(command)
    self.assertEqual(tokens, expected_tokens)

    command = 'command subcommand parameter |pipe'
    tokens = self.cmd._SplitCommandLine(command)
    self.assertEqual(tokens, expected_tokens)

    command = 'command subcommand parameter|pipe'
    tokens = self.cmd._SplitCommandLine(command)
    self.assertEqual(tokens, expected_tokens)

    command = 'command subcommand "parameter| parameter"|pipe \\" \\\\'
    tokens = self.cmd._SplitCommandLine(command)
    expected_tokens = ['command', 'subcommand', 'parameter| parameter', '|',
                       'pipe', '"', '\\']
    self.assertEqual(tokens, expected_tokens)


class ShellCommandTest(unittest.TestCase):
  def testShellCommand(self):
    cmd = squires.ShellCommand('blah')
    self.assertEqual({'<command>': 'Shell command to pipe output through'},
                     cmd.Completer(['some', 'command']))
    # Proper testing is as follows:
    # - Generating a temporary filename.
    # - Opening a pipe to cat to that filename.
    # - Printing text to 'stdout'
    # - Closing the pipe and verifying the file contents.
    testtext = 'This is a test'
    tmpfile = tempfile.mkstemp()[1]
    cmd._StartPipe("cat > %s" % tmpfile)
    print(testtext)
    cmd._StopPipe()
    print('Test data.')  # Should not be in shell pipeline.
    return
    try:
      self.assertEqual(testtext, open(tmpfile).read())
    finally:
      os.remove(tmpfile)


if __name__ == '__main__':
  unittest.main()
