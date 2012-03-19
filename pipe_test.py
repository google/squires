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

import pipe
import sys


class TestPipe(pipe.Pipe):

  def __init__(self):
    self.begin = None
    self.end = None
    self.flush = None
    self.string = ''

  def Begin(self):
    self.begin = True

  def End(self):
    self.end = True

  def write(self, string):
    self.string += string

  def flush(self):
    self.flush = True


class PipeTest(unittest.TestCase):

  def testPipe(self):

    class DummyCommand(object):
      RETVALS = {
          'start': False,
          'stop': False,
      }

      def GetOption(self, name):
        return DummyCommand.RETVALS[name]

    tpipe = TestPipe()

    # Ensure pipe gets started
    DummyCommand.RETVALS['start'] = True
    self.assertTrue(tpipe.State(DummyCommand(), None))
    self.assertTrue(tpipe.begin)

    # Stdout should redirect to the pipe
    print 'Hello, world'
    self.assertEqual('Hello, world\n', tpipe.string)

    # Verify pipe stope correctly.
    DummyCommand.RETVALS['start'] = False
    DummyCommand.RETVALS['stop'] = True
    self.assertTrue(tpipe.State(DummyCommand(), None))
    self.assertTrue(tpipe.end)

    # Stdout should not redirect any more.
    print 'Pipe stdout test'
    self.assertEqual('Hello, world\n', tpipe.string)

  def testPipes(self):
    class DummyCommand(object):

      def __init__(self):
        self.options = {}

      def SetExpected(self, option, value):
        self.options[option] = value

      def GetOption(self, name):
        return self.options.get(name)

    # Test 'grep'
    op = pipe.Pipe.write
    tp = TestPipe()
    pipe.Pipe.write = tp.write

    cmd = DummyCommand()
    cmd.SetExpected('start', True)
    cmd.SetExpected('stop', False)
    cmd.SetExpected('string', '[0-9]+')

    greppipe = pipe.GrepPipe()
    greppipe.State(cmd, None)
    self.failIfEqual(None, greppipe.regex)
    greppipe.write('This should not match\n')
    self.assertEqual('', tp.string)
    greppipe.write('22 should match\n')
    self.assertEqual('22 should match\n', tp.string)
    pipe.Pipe.write = op

    # Test 'except'
    ow = sys.__stdout__
    tp = TestPipe()
    sys.__stdout__ = tp

    cmd = DummyCommand()
    cmd.SetExpected('start', True)
    cmd.SetExpected('stop', False)
    cmd.SetExpected('string', '[0-9]+')

    exceptpipe = pipe.ExceptPipe()
    exceptpipe.State(cmd, None)
    self.failIfEqual(None, exceptpipe.regex)
    exceptpipe.write('11 This should not match\n')
    self.assertEqual('', tp.string)
    exceptpipe.write('This should match\n')
    self.assertEqual('This should match\n', tp.string)
    sys.__stdout__ = ow

    # Test 'count'
    op = pipe.Pipe.write
    tp = TestPipe()
    pipe.Pipe.write = tp.write

    cmd = DummyCommand()
    cmd.SetExpected('start', True)
    cmd.SetExpected('stop', False)
    countpipe = pipe.CountPipe()
    countpipe.State(cmd, None)
    countpipe.write('One line\n')
    self.assertEqual(1, countpipe.linecount)
    countpipe.write('Another line\n')
    cmd.SetExpected('start', False)
    cmd.SetExpected('stop', True)
    countpipe.State(cmd, None)
    self.assertEqual(2, countpipe.linecount)

    pipe.Pipe.write = op

    # Test 'sh'
    op = pipe.Pipe.write
    tp = TestPipe()
    pipe.Pipe.write = tp.write

    cmd = DummyCommand()
    cmd.SetExpected('start', True)
    cmd.SetExpected('stop', False)
    cmd.SetExpected('string', 'cat > /tmp/squires_test.log')
    shpipe = pipe.ShellPipe()
    if os.path.exists('/tmp/squires_test.log'):
      os.remove('/tmp/squires_test.log')
    shpipe.State(cmd, None)
    shpipe.write('One line\n')
    cmd.SetExpected('start', False)
    cmd.SetExpected('stop', True)
    shpipe.State(cmd, None)
    pipe.Pipe.write = op
    self.assertTrue(os.path.exists('/tmp/squires_test.log'))
    self.assertTrue('One line' in open('/tmp/squires_test.log').read())
    os.remove('/tmp/squires_test.log')


if __name__ == '__main__':
  unittest.main()
