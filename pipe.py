# Copyright 2011 Google Inc. All Rights Reserved.

"""Pipe support code for Squires.

This module contains code for building and handling of
pipes, ie 'command | modifier'.
"""
#TODO(bbuxton): Support chaining pipes.
__author__ = 'bbuxton@google.com (Ben Buxton)'

import re
import subprocess
import sys

# Character used as a pipe to split command line
PIPE_CHAR = '|'


def SplitByPipe(line):
  """Splits a line by the PIPE_CHAR.

  Args:
    line: A list of strings, the command line.

  Returns:
    A tuple. The first entry is a list of strings before the
    PIPE_CHAR. The second entry is a list of strings after the
    PIPE_CHAR.
  """
  if PIPE_CHAR in line:
    return (line[:line.index(PIPE_CHAR)],
            line[line.index(PIPE_CHAR)+1:])
  return line


class Pipe(object):
  """The base object that represents pipes.

  Any pipe commands should have an instance of this used as
  the .pipe attribute. This object will then be used for piping.

  Attributes:
    cmd: A Command() object, the pipe command.
  """
  def State(self, cmd, unused_args):
    """Called at setup and teardown of the pipe.

    Immediately before the main command is run, this
    method is called, with either the 'start' or 'stop'
    option.

    Args:
      cmd: A Command object, the command being run,

    Returns:
      A boolean. If True, the state was set sucessfully.
    """
    self.cmd = cmd
    success = False
    if self.cmd.GetOption('start'):
      success = self.Begin()
      self.SetStdout(self)
    if self.cmd.GetOption('stop'):
      self.ResetStdout()
      success = self.End()
    return success is not False

  def SetStdout(self, fdesc):
    """Sets stdout to 'fdesc'."""
    # TODO(bbuxton): Better stdin/stdout support for pipe chaining.
    self.old_stdout = sys.stdout
    sys.stdout = fdesc

  def ResetStdout(self):
    """Sets stdout to 'fdesc'."""
    sys.stdout = self.old_stdout

  def write(self, string):
    """Overwrites sys.stdout.write."""
    sys.__stdout__.write(string)

  def flush(self):
    """Overwrites sys.stdout.flush."""
    sys.__stdout__.flush()

  def Begin(self):
    """Called as the pipe is set up.

    Returns:
      A boolean. If not False, setup was successful.
    """
    return True

  def End(self):
    """Called as the pipe is set up.

    Returns:
      A boolean. If not False, setup was successful.
    """
    return True


class GrepPipe(Pipe):
  """A grep pipe, prints lines that match."""

  def Begin(self):
    self.regex = re.compile(self.cmd.GetOption('string'), re.I)
    self.linebuffer = []

  def write(self, string):
    self.linebuffer.append(string)
    if '\n' in string:
      if self.regex.search(''.join(self.linebuffer)):
        super(GrepPipe, self).write(''.join(self.linebuffer))
      self.linebuffer = []

  def End(self):
    if '\n' in self.linebuffer:
      super(GrepPipe, self).write(''.join(self.linebuffer))


class ExceptPipe(GrepPipe):
  """An except pipe, prints lines that do not match."""

  def write(self, string):
    self.linebuffer.append(string)
    if '\n' in string:
      if not self.regex.search(''.join(self.linebuffer)):
        sys.__stdout__.write(''.join(self.linebuffer))
      self.linebuffer = []


class CountPipe(Pipe):
  """Count pipe, prints number of lines output."""

  def Begin(self):
    self.linecount = 0

  def write(self, string):
    self.linecount += string.count('\n')

  def End(self):
    super(CountPipe, self).write('Count: %d\n' % self.linecount)


class ShellPipe(Pipe):
  """Pipe output through a shell command."""

  def Begin(self):
    # Get shell command, and open it, redirecting stdin
    cmd = self.cmd.GetOption('string')
    self.pipe = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE)

  def write(self, string):
    # Write to the pipe.
    self.pipe.stdin.write(string)

  def End(self):
    # Close stdin and wait for subprocess to end.
    self.pipe.stdin.close()
    self.pipe.wait()
    del self.pipe


class MorePipe(ShellPipe):
  """Display output one page at a time."""

  def Begin(self):
    # Just pipe through shell "more"
    self.pipe = subprocess.Popen('more -', shell=True, stdin=subprocess.PIPE)
